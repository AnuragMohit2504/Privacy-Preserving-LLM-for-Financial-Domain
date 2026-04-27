"""
Financial Document Analyzer using Ollama
Analyzes 1000 bank statement PDFs and single payslip CSV with 1000 rows
"""

import os
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import re
from typing import Dict, List, Tuple
import PyPDF2
import requests
from collections import defaultdict

class FinancialAnalyzer:
    def __init__(self, ollama_model="llama3.2", ollama_url="http://localhost:11434"):
        """
        Initialize the analyzer with Ollama configuration
        
        Args:
            ollama_model: Model name (llama3.2, mistral, phi3, etc.)
            ollama_url: Ollama API endpoint
        """
        self.ollama_model = ollama_model
        self.ollama_url = ollama_url
        self.bank_data = []
        self.payslip_df = None
        
    def extract_bank_statement_pdf(self, pdf_path: str) -> Dict:
        """Extract data from bank statement PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
            
            # Parse the extracted text
            data = self._parse_bank_statement_text(text)
            data['source_file'] = os.path.basename(pdf_path)
            return data
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            return None
    
    def _parse_bank_statement_text(self, text: str) -> Dict:
        """Parse bank statement text to extract structured data"""
        data = {
            'account_holder': '',
            'account_number': '',
            'statement_period': '',
            'transactions': [],
            'opening_balance': 0,
            'closing_balance': 0,
            'total_credits': 0,
            'total_debits': 0,
            'transaction_count': 0
        }
        
        # Extract account holder
        holder_match = re.search(r'Account Holder:\s*(.+)', text)
        if holder_match:
            data['account_holder'] = holder_match.group(1).strip()
        
        # Extract account number
        acc_match = re.search(r'Account No\.:\s*(\d+)', text)
        if acc_match:
            data['account_number'] = acc_match.group(1).strip()
        
        # Extract statement period
        period_match = re.search(r'Statement Period:\s*(.+)', text)
        if period_match:
            data['statement_period'] = period_match.group(1).strip()
        
        # Extract transactions (improved pattern matching)
        lines = text.split('\n')
        for line in lines:
            # Match date pattern at start of line
            if re.match(r'\d{2}-[A-Za-z]{3}-\d{4}', line):
                try:
                    # More flexible parsing
                    parts = re.split(r'\s+', line.strip())
                    if len(parts) >= 4:
                        # Find numeric values
                        amounts = []
                        for part in parts[1:]:
                            cleaned = part.replace('Rs.', '').replace(',', '').strip()
                            if cleaned and (cleaned.replace('.', '').replace('-', '').isdigit() or cleaned == '-'):
                                amounts.append(cleaned)
                        
                        if len(amounts) >= 3:
                            withdrawal = 0 if amounts[-3] == '-' else float(amounts[-3])
                            deposit = 0 if amounts[-2] == '-' else float(amounts[-2])
                            balance = float(amounts[-1])
                            
                            # Extract description (everything between date and amounts)
                            desc_start = len(parts[0]) + 1
                            desc_end = line.rfind(amounts[-3])
                            description = line[desc_start:desc_end].strip()
                            
                            transaction = {
                                'date': parts[0],
                                'description': description,
                                'withdrawal': withdrawal,
                                'deposit': deposit,
                                'balance': balance
                            }
                            data['transactions'].append(transaction)
                except Exception as e:
                    continue
        
        # Calculate totals
        if data['transactions']:
            data['total_credits'] = sum(t['deposit'] for t in data['transactions'])
            data['total_debits'] = sum(t['withdrawal'] for t in data['transactions'])
            data['transaction_count'] = len(data['transactions'])
            data['opening_balance'] = data['transactions'][0]['balance'] - data['transactions'][0]['deposit'] + data['transactions'][0]['withdrawal']
            data['closing_balance'] = data['transactions'][-1]['balance']
        
        return data
    
    def load_payslip_csv(self, csv_path: str) -> pd.DataFrame:
        """Load the single payslip CSV with 1000 rows"""
        try:
            df = pd.read_csv(csv_path)
            # Clean column names (remove extra spaces)
            df.columns = df.columns.str.strip()
            print(f"Loaded payslip CSV with {len(df)} rows and {len(df.columns)} columns")
            print(f"Columns: {list(df.columns)}")
            return df
        except Exception as e:
            print(f"Error loading {csv_path}: {e}")
            return None
    
    def batch_process_bank_statements(self, folder_path: str, limit=None):
        """Process all bank statement PDFs in a folder"""
        folder = Path(folder_path)
        pdf_files = sorted(list(folder.glob("*.pdf")))
        
        if limit:
            pdf_files = pdf_files[:limit]
        
        print(f"Found {len(pdf_files)} bank statement PDFs...")
        print("Processing (this may take a few minutes)...")
        
        for i, pdf_file in enumerate(pdf_files, 1):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(pdf_files)} statements...")
            
            data = self.extract_bank_statement_pdf(str(pdf_file))
            if data and data['transactions']:
                self.bank_data.append(data)
        
        print(f"\n✓ Successfully processed {len(self.bank_data)} bank statements")
        print(f"  Total transactions extracted: {sum(len(s['transactions']) for s in self.bank_data)}")
        return self.bank_data
    
    def analyze_bank_patterns(self) -> Dict:
        """Comprehensive analysis of all bank statements"""
        if not self.bank_data:
            return {}
        
        all_transactions = []
        for statement in self.bank_data:
            all_transactions.extend(statement['transactions'])
        
        # Categorize transactions intelligently
        categories = defaultdict(list)
        category_keywords = {
            'UPI_Payments': ['UPI/', 'UPI-'],
            'Food_Delivery': ['SWIGGY', 'ZOMATO', 'UBER EATS'],
            'Ride_Sharing': ['UBER', 'OLA', 'RAPIDO'],
            'Entertainment': ['SPOTIFY', 'NETFLIX', 'PRIME', 'HOTSTAR', 'YOUTUBE'],
            'Shopping': ['AMAZON', 'FLIPKART', 'MYNTRA', 'AJIO'],
            'Salary': ['SALARY', 'WIPRO', 'TCS', 'INFOSYS', 'COGNIZANT'],
            'Transfers': ['TRANSFER', 'NEFT', 'IMPS', 'RTGS'],
            'Restaurants': ['RESTAURANT', 'CAFE', 'FOOD'],
            'Medical': ['MEDICAL', 'PHARMACY', 'HOSPITAL', 'APOLLO', 'MEDPLUS'],
            'Utilities': ['ELECTRICITY', 'WATER', 'GAS', 'BILL'],
            'Investment': ['MUTUAL FUND', 'SIP', 'STOCK', 'ZERODHA', 'GROWW']
        }
        
        for txn in all_transactions:
            desc = txn['description'].upper()
            categorized = False
            
            for category, keywords in category_keywords.items():
                if any(keyword in desc for keyword in keywords):
                    categories[category].append(txn)
                    categorized = True
                    break
            
            if not categorized:
                categories['Other'].append(txn)
        
        # Calculate comprehensive statistics
        analysis = {
            'summary': {
                'total_statements': len(self.bank_data),
                'total_transactions': len(all_transactions),
                'total_spent': sum(t['withdrawal'] for t in all_transactions),
                'total_earned': sum(t['deposit'] for t in all_transactions),
                'avg_transaction_value': np.mean([t['withdrawal'] for t in all_transactions if t['withdrawal'] > 0]),
                'net_cashflow': sum(t['deposit'] - t['withdrawal'] for t in all_transactions)
            },
            'spending_by_category': {},
            'monthly_trends': {},
            'top_expenses': [],
            'savings_rate': 0
        }
        
        # Category-wise breakdown
        for cat, txns in categories.items():
            if txns:
                total_spent = sum(t['withdrawal'] for t in txns)
                total_earned = sum(t['deposit'] for t in txns)
                
                analysis['spending_by_category'][cat] = {
                    'transaction_count': len(txns),
                    'total_spent': total_spent,
                    'total_earned': total_earned,
                    'avg_per_transaction': total_spent / len([t for t in txns if t['withdrawal'] > 0]) if any(t['withdrawal'] > 0 for t in txns) else 0,
                    'percentage_of_total': (total_spent / analysis['summary']['total_spent'] * 100) if analysis['summary']['total_spent'] > 0 else 0
                }
        
        # Top 10 expenses
        all_debits = [t for t in all_transactions if t['withdrawal'] > 0]
        top_10 = sorted(all_debits, key=lambda x: x['withdrawal'], reverse=True)[:10]
        analysis['top_expenses'] = [
            {'date': t['date'], 'description': t['description'], 'amount': t['withdrawal']}
            for t in top_10
        ]
        
        # Calculate savings rate
        if analysis['summary']['total_earned'] > 0:
            analysis['savings_rate'] = ((analysis['summary']['total_earned'] - analysis['summary']['total_spent']) / analysis['summary']['total_earned']) * 100
        
        return analysis
    
    def analyze_payslip_patterns(self) -> Dict:
        """Comprehensive analysis of payslip data (1000 rows)"""
        if self.payslip_df is None or self.payslip_df.empty:
            return {}
        
        df = self.payslip_df
        
        analysis = {
            'summary': {
                'total_records': len(df),
                'avg_net_pay': df['Net_Pay'].mean(),
                'median_net_pay': df['Net_Pay'].median(),
                'avg_gross_earnings': df['Gross_Earnings'].mean(),
                'avg_total_deductions': df['Total_Deductions'].mean(),
                'deduction_percentage': (df['Total_Deductions'].mean() / df['Gross_Earnings'].mean() * 100)
            },
            'salary_trends': {},
            'deduction_breakdown': {},
            'yearly_comparison': {},
            'bonus_analysis': {}
        }
        
        # Monthly salary trends
        if 'Month' in df.columns and 'Year' in df.columns:
            monthly_avg = df.groupby(['Year', 'Month'])['Net_Pay'].agg(['mean', 'count']).to_dict()
            analysis['salary_trends'] = monthly_avg
        
        # Deduction component analysis
        deduction_cols = ['PF', 'TDS', 'Insurance', 'Loan_Deductions', 'Advance_Deductions', 'Misc_Deductions']
        available_cols = [col for col in deduction_cols if col in df.columns]
        
        for col in available_cols:
            analysis['deduction_breakdown'][col] = {
                'average': df[col].mean(),
                'total': df[col].sum(),
                'max': df[col].max(),
                'min': df[col].min()
            }
        
        # Yearly comparison
        if 'Year' in df.columns:
            yearly_stats = df.groupby('Year').agg({
                'Net_Pay': ['mean', 'sum', 'count'],
                'Gross_Earnings': 'mean',
                'Total_Deductions': 'mean'
            }).to_dict()
            analysis['yearly_comparison'] = yearly_stats
        
        # Bonus analysis
        if 'Bonus' in df.columns:
            bonus_data = df[df['Bonus'] > 0]
            if not bonus_data.empty:
                analysis['bonus_analysis'] = {
                    'total_bonus_received': bonus_data['Bonus'].sum(),
                    'avg_bonus': bonus_data['Bonus'].mean(),
                    'bonus_frequency': len(bonus_data),
                    'months_with_bonus': bonus_data['Month'].unique().tolist() if 'Month' in bonus_data.columns else []
                }
        
        return analysis
    
    def generate_comprehensive_insights(self, bank_analysis: Dict, payslip_analysis: Dict) -> str:
        """Generate detailed AI insights using Ollama"""
        
        # Helper function to convert numpy types to Python types
        def convert_to_json_serializable(obj):
            import json
            return json.loads(json.dumps(obj, default=str))
        
        # Prepare comprehensive context
        context = f"""
# Financial Data Analysis Report

## Bank Statement Summary (from {bank_analysis.get('summary', {}).get('total_statements', 0)} statements):
- Total Transactions: {bank_analysis.get('summary', {}).get('total_transactions', 0)}
- Total Money Spent: Rs. {bank_analysis.get('summary', {}).get('total_spent', 0):,.2f}
- Total Money Earned: Rs. {bank_analysis.get('summary', {}).get('total_earned', 0):,.2f}
- Net Cash Flow: Rs. {bank_analysis.get('summary', {}).get('net_cashflow', 0):,.2f}
- Savings Rate: {bank_analysis.get('savings_rate', 0):.2f}%

## Spending Breakdown by Category:
{json.dumps(convert_to_json_serializable(bank_analysis.get('spending_by_category', {})), indent=2)}

## Top 5 Expenses:
{json.dumps(convert_to_json_serializable(bank_analysis.get('top_expenses', [])[:5]), indent=2)}

## Payslip Summary (from {payslip_analysis.get('summary', {}).get('total_records', 0)} records):
- Average Net Salary: Rs. {payslip_analysis.get('summary', {}).get('avg_net_pay', 0):,.2f}
- Average Gross Earnings: Rs. {payslip_analysis.get('summary', {}).get('avg_gross_earnings', 0):,.2f}
- Average Deductions: Rs. {payslip_analysis.get('summary', {}).get('avg_total_deductions', 0):,.2f}
- Deduction Percentage: {payslip_analysis.get('summary', {}).get('deduction_percentage', 0):.2f}%

## Deduction Breakdown:
{json.dumps(convert_to_json_serializable(payslip_analysis.get('deduction_breakdown', {})), indent=2)}

## Bonus Information:
{json.dumps(convert_to_json_serializable(payslip_analysis.get('bonus_analysis', {})), indent=2)}
"""
        
        prompt = """As a financial advisor, analyze this data and provide:

1. **Financial Health Score** (0-100) with explanation
2. **Top 3 Spending Concerns** and specific recommendations
3. **Savings Opportunities** - where can they save money?
4. **Income vs Spending Analysis** - is the balance healthy?
5. **Tax Optimization** suggestions based on deductions
6. **Budget Recommendations** for each major category
7. **Financial Goals** they should focus on

Be specific, actionable, and data-driven in your analysis."""
        
        return self.query_ollama(prompt, context)
    
    def query_ollama(self, prompt: str, context: str = "") -> str:
        """Send query to Ollama and get response"""
        try:
            full_prompt = f"{context}\n\n{prompt}\n\nProvide detailed analysis:"
            
            print("\nQuerying Ollama AI... (this may take 30-60 seconds)")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=180
            )
            
            if response.status_code == 200:
                return response.json()['response']
            else:
                return f"Error: {response.status_code} - {response.text}"
        except requests.exceptions.ConnectionError:
            return "Error: Cannot connect to Ollama. Make sure Ollama is running (run 'ollama serve' in terminal)"
        except Exception as e:
            return f"Error querying Ollama: {e}"
    
    def export_results(self, output_folder: str, bank_analysis: Dict, payslip_analysis: Dict, insights: str):
        """Export all analysis results to files"""
        os.makedirs(output_folder, exist_ok=True)
        
        # Helper to convert complex objects to JSON-serializable format
        def make_serializable(obj):
            if isinstance(obj, dict):
                return {str(k): make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif hasattr(obj, 'item'):  # numpy types
                return obj.item()
            elif isinstance(obj, (np.integer, np.floating)):
                return float(obj)
            else:
                return obj
        
        # Export bank analysis
        with open(f"{output_folder}/bank_analysis.json", 'w') as f:
            json.dump(make_serializable(bank_analysis), f, indent=2, default=str)
        
        # Export payslip analysis
        with open(f"{output_folder}/payslip_analysis.json", 'w') as f:
            json.dump(make_serializable(payslip_analysis), f, indent=2, default=str)
        
        # Export AI insights
        with open(f"{output_folder}/ai_insights.txt", 'w', encoding='utf-8') as f:
            f.write(insights)
        
        # Export summary report
        with open(f"{output_folder}/summary_report.txt", 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FINANCIAL ANALYSIS SUMMARY REPORT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Bank Statements Analyzed: {bank_analysis.get('summary', {}).get('total_statements', 0)}\n")
            f.write(f"Payslip Records Analyzed: {payslip_analysis.get('summary', {}).get('total_records', 0)}\n")
            f.write("\n" + "=" * 80 + "\n")
            f.write(insights)
        
        print(f"\n✓ Results exported to '{output_folder}/' folder")
        print(f"  - bank_analysis.json")
        print(f"  - payslip_analysis.json")
        print(f"  - ai_insights.txt")
        print(f"  - summary_report.txt")


def main():
    """Main execution function"""
    print("=" * 80)
    print("FINANCIAL DOCUMENT ANALYZER WITH OLLAMA AI")
    print("=" * 80)
    
    # Initialize analyzer
    analyzer = FinancialAnalyzer(ollama_model="llama3.2")
    
    # Process bank statements (1000 PDFs)
    print("\n[STEP 1] Processing Bank Statement PDFs...")
    bank_folder = "./bank_statements"
    if os.path.exists(bank_folder):
        analyzer.batch_process_bank_statements(bank_folder)
        
        print("\n[STEP 2] Analyzing Bank Transaction Patterns...")
        bank_analysis = analyzer.analyze_bank_patterns()
        
        print(f"\n📊 Bank Analysis Summary:")
        print(f"   Total Spent: Rs. {bank_analysis['summary']['total_spent']:,.2f}")
        print(f"   Total Earned: Rs. {bank_analysis['summary']['total_earned']:,.2f}")
        print(f"   Savings Rate: {bank_analysis.get('savings_rate', 0):.2f}%")
    else:
        print(f"⚠ Warning: Bank statements folder not found at '{bank_folder}'")
        bank_analysis = {}
    
    # Process payslip CSV (1 file with 1000 rows)
    print("\n[STEP 3] Processing Payslip CSV...")
    payslip_file = "C:\\Users\\anura\\Desktop\\FINGPT_MAJOR_PROJECT\\data\\generators\\enhanced_payslips.csv"
    if os.path.exists(payslip_file):
        analyzer.payslip_df = analyzer.load_payslip_csv(payslip_file)
        
        print("\n[STEP 4] Analyzing Payslip Data...")
        payslip_analysis = analyzer.analyze_payslip_patterns()
        
        print(f"\n💰 Payslip Analysis Summary:")
        print(f"   Avg Net Pay: Rs. {payslip_analysis['summary']['avg_net_pay']:,.2f}")
        print(f"   Avg Deductions: Rs. {payslip_analysis['summary']['avg_total_deductions']:,.2f}")
        print(f"   Deduction %: {payslip_analysis['summary']['deduction_percentage']:.2f}%")
    else:
        print(f"⚠ Warning: Payslip CSV not found at '{payslip_file}'")
        payslip_analysis = {}
    
    # Generate AI insights
    if bank_analysis or payslip_analysis:
        print("\n" + "=" * 80)
        print("[STEP 5] Generating AI-Powered Financial Insights...")
        print("=" * 80)
        
        insights = analyzer.generate_comprehensive_insights(bank_analysis, payslip_analysis)
        print("\n" + insights)
        
        # Export all results
        print("\n[STEP 6] Exporting Results...")
        analyzer.export_results("./analysis_results", bank_analysis, payslip_analysis, insights)
    else:
        print("\n⚠ No data to analyze. Please check file paths.")
    
    print("\n" + "=" * 80)
    print("✓ Analysis Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()