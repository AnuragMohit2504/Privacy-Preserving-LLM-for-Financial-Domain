import pandas as pd
import numpy as np
import PyPDF2
import re
from datetime import datetime
import pickle

def safe_float_convert(value, default=0.0):
    """Safely convert value to float with fallback"""
    try:
        if value is None or value == '' or value == 'nan':
            return default
        if isinstance(value, str):
            value = value.replace(',', '').replace('Rs.', '').replace('Rs', '').strip()
            if not value:
                return default
        return float(value)
    except (ValueError, TypeError, AttributeError):
        return default

def extract_bank_statement_features_csv(filepath):
    """Extract features from CSV bank statement"""
    try:
        if filepath.lower().endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        else:
            df = pd.read_csv(filepath)
        
        amount_cols = [col for col in df.columns if any(word in col.lower() 
                       for word in ['amount', 'debit', 'credit', 'balance', 'withdrawal', 'deposit'])]
        
        features = {}
        
        if amount_cols:
            for col in amount_cols:
                amounts = pd.to_numeric(df[col], errors='coerce').dropna()
                if len(amounts) > 0:
                    features[f'{col}_sum'] = safe_float_convert(amounts.sum())
                    features[f'{col}_mean'] = safe_float_convert(amounts.mean())
                    features[f'{col}_std'] = safe_float_convert(amounts.std())
                    features[f'{col}_max'] = safe_float_convert(amounts.max())
                    features[f'{col}_min'] = safe_float_convert(amounts.min())
        
        features['total_transactions'] = len(df)
        
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        if date_cols:
            try:
                df[date_cols[0]] = pd.to_datetime(df[date_cols[0]], errors='coerce')
                valid_dates = df[date_cols[0]].dropna()
                if len(valid_dates) > 1:
                    date_range = (valid_dates.max() - valid_dates.min()).days
                    features['date_range_days'] = safe_float_convert(date_range)
            except:
                features['date_range_days'] = 0.0
        
        feature_vector = np.array([
            features.get('amount_sum', 0.0),
            features.get('amount_mean', 0.0),
            features.get('amount_std', 0.0),
            features.get('amount_max', 0.0),
            features.get('amount_min', 0.0),
            features.get('total_transactions', 0.0),
            features.get('date_range_days', 0.0),
            features.get('debit_sum', features.get('withdrawal_sum', 0.0)),
            features.get('credit_sum', features.get('deposit_sum', 0.0)),
            features.get('balance_mean', 0.0)
        ], dtype=np.float32)
        
        return feature_vector, features
        
    except Exception as e:
        raise ValueError(f"CSV feature extraction failed: {str(e)}")

def extract_bank_statement_features_pdf(filepath):
    """Extract features from PDF bank statement with robust parsing"""
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text or len(text.strip()) < 100:
            raise ValueError("PDF text extraction failed or insufficient content")
        
        # Extract all amounts with Rs. prefix
        amount_pattern = r'Rs\.?\s*([\d,]+\.?\d{0,2})'
        matches = re.findall(amount_pattern, text, re.IGNORECASE)
        
        amounts = []
        for match in matches:
            amount = safe_float_convert(match)
            if amount > 0:
                amounts.append(amount)
        
        if not amounts:
            amounts = [0.0]
        
        # Categorize transactions
        withdrawals = []
        deposits = []
        balances = []
        
        withdrawal_keywords = ['withdrawal', 'payment', 'debit', 'restaurant', 'grocery', 
                              'fuel', 'bill', 'emi', 'shopping', 'atm', 'rent', 'entertainment',
                              'medical', 'pharmacy', 'clothing', 'uber', 'ola', 'swiggy',
                              'electricity', 'internet', 'mobile']
        deposit_keywords = ['deposit', 'credit', 'salary', 'refund', 'transfer', 'income']
        balance_keywords = ['balance']
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            
            # Find amounts in this line
            line_amounts = re.findall(r'rs\.?\s*([\d,]+\.?\d{0,2})', line, re.IGNORECASE)
            
            for amt_str in line_amounts:
                amount = safe_float_convert(amt_str)
                if amount <= 0:
                    continue
                
                # Categorize based on keywords
                if any(kw in line_lower for kw in withdrawal_keywords):
                    withdrawals.append(amount)
                elif any(kw in line_lower for kw in deposit_keywords):
                    deposits.append(amount)
                elif any(kw in line_lower for kw in balance_keywords):
                    balances.append(amount)
        
        # Ensure we have at least some data
        if not withdrawals:
            withdrawals = [0.0]
        if not deposits:
            deposits = [0.0]
        if not balances:
            balances = amounts[-5:] if len(amounts) >= 5 else amounts
            if not balances:
                balances = [0.0]
        
        # Count transactions (lines with dates or transaction patterns)
        transaction_count = len([line for line in lines 
                                if re.search(r'\d{2}-\w{3}-\d{4}|\d{2}/\d{2}/\d{4}', line)])
        
        if transaction_count == 0:
            transaction_count = len(amounts)
        
        # Calculate features
        features = {
            'amounts_sum': safe_float_convert(np.sum(amounts)),
            'amounts_mean': safe_float_convert(np.mean(amounts)),
            'amounts_std': safe_float_convert(np.std(amounts)),
            'amounts_max': safe_float_convert(np.max(amounts)),
            'amounts_min': safe_float_convert(np.min(amounts)),
            'transaction_count': safe_float_convert(transaction_count),
            'withdrawals_sum': safe_float_convert(np.sum(withdrawals)),
            'deposits_sum': safe_float_convert(np.sum(deposits)),
            'balance_mean': safe_float_convert(np.mean(balances)),
            'withdrawal_count': safe_float_convert(len([w for w in withdrawals if w > 0]))
        }
        
        # Create feature vector
        feature_vector = np.array([
            features['amounts_sum'],
            features['amounts_mean'],
            features['amounts_std'],
            features['amounts_max'],
            features['amounts_min'],
            features['transaction_count'],
            features['withdrawals_sum'],
            features['deposits_sum'],
            features['balance_mean'],
            features['withdrawal_count']
        ], dtype=np.float32)
        
        # Validate feature vector
        if np.any(np.isnan(feature_vector)):
            feature_vector = np.nan_to_num(feature_vector, nan=0.0)
        
        if np.all(feature_vector == 0):
            raise ValueError("All features are zero - PDF parsing may have failed")
        
        return feature_vector, features
        
    except Exception as e:
        raise ValueError(f"PDF feature extraction failed: {str(e)}")

def extract_payslip_features_pdf(filepath):
    """Extract features from PDF payslip"""
    try:
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text or len(text.strip()) < 50:
            raise ValueError("PDF text extraction failed or insufficient content")
        
        text_lower = text.lower()
        
        features = {}
        
        # Salary component keywords and patterns
        salary_patterns = {
            'basic': r'basic[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'hra': r'hra[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'gross': r'gross[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'net': r'net[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'ctc': r'ctc[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'deduction': r'deduction[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'pf': r'pf[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})',
            'tax': r'tax[:\s]+rs\.?\s*([\d,]+\.?\d{0,2})'
        }
        
        for key, pattern in salary_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                features[key] = safe_float_convert(match.group(1))
            else:
                features[key] = 0.0
        
        # Calculate derived features
        gross = features.get('gross', 0)
        deduction = features.get('deduction', 0)
        net = features.get('net', 0)
        
        take_home = gross - deduction if gross > 0 else net
        net_to_gross_ratio = net / gross if gross > 0 else 0.0
        
        feature_vector = np.array([
            features.get('basic', 0),
            features.get('hra', 0),
            features.get('gross', 0),
            features.get('net', 0),
            features.get('ctc', 0),
            features.get('deduction', 0),
            features.get('pf', 0),
            features.get('tax', 0),
            take_home,
            safe_float_convert(net_to_gross_ratio)
        ], dtype=np.float32)
        
        # Validate
        if np.any(np.isnan(feature_vector)):
            feature_vector = np.nan_to_num(feature_vector, nan=0.0)
        
        return feature_vector, features
        
    except Exception as e:
        raise ValueError(f"Payslip feature extraction failed: {str(e)}")

def extract_features(filepath, file_type, analysis_type):
    """Main feature extraction dispatcher"""
    try:
        if analysis_type == 'payslip' or 'payslip' in filepath.lower():
            return extract_payslip_features_pdf(filepath)
        elif file_type in {'csv', 'xlsx', 'xls'}:
            return extract_bank_statement_features_csv(filepath)
        elif file_type == 'pdf':
            return extract_bank_statement_features_pdf(filepath)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    except Exception as e:
        raise ValueError(f"Feature extraction error: {str(e)}")

def serialize_features(feature_vector):
    """Serialize numpy array for transmission"""
    return pickle.dumps(feature_vector)

def deserialize_features(feature_bytes):
    """Deserialize transmitted features"""
    return pickle.loads(feature_bytes)
