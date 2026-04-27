import random
from datetime import datetime, timedelta
from fpdf import FPDF
import os
import json

class EnhancedBankStatementGenerator:
    def __init__(self):
        self.banks = ['HDFC Bank', 'ICICI Bank', 'SBI', 'Axis Bank', 'Kotak Mahindra', 
                      'YES Bank', 'IndusInd Bank', 'Bank of Baroda']
        self.branches = [
            'Andheri, Mumbai', 'Koramangala, Bengaluru', 'Connaught Place, Delhi',
            'Anna Nagar, Chennai', 'Banjara Hills, Hyderabad', 'Salt Lake, Kolkata',
            'Vastrapur, Ahmedabad', 'MG Road, Pune', 'Jubilee Hills, Hyderabad'
        ]
        self.names = [
            'Rahul Sharma', 'Priya Patel', 'Amit Kumar', 'Sneha Reddy', 'Vikram Singh',
            'Anjali Gupta', 'Rohan Mehta', 'Kavya Iyer', 'Arjun Nair', 'Pooja Joshi',
            'Karan Shah', 'Divya Verma', 'Nikhil Desai', 'Ritu Malhotra', 'Sanjay Kapoor',
            'Neha Singh', 'Aditya Chopra', 'Megha Agarwal', 'Varun Khanna', 'Shruti Kumari',
            'Isha Mehta', 'Kunal Jain', 'Ananya Roy', 'Siddharth Pillai'
        ]
        self.companies = [
            'TCS Ltd', 'Infosys Technologies', 'Wipro Corp', 'Tech Mahindra',
            'Cognizant India', 'HCL Technologies', 'Capgemini India', 'Accenture India',
            'Amazon India', 'Google India', 'Microsoft India', 'Flipkart', 'Paytm',
            'Ola Cabs', 'Swiggy', 'Zomato', 'BYJU\'S', 'Razorpay'
        ]
        
        # Customer profiles with spending behavior
        self.customer_profiles = {
            'frugal_saver': {'expense_factor': 0.4, 'savings_rate': 0.3, 'description': 'Conservative spender, high savings'},
            'moderate': {'expense_factor': 0.65, 'savings_rate': 0.15, 'description': 'Balanced spending and saving'},
            'spender': {'expense_factor': 0.85, 'savings_rate': 0.05, 'description': 'High spender, low savings'},
            'investor': {'expense_factor': 0.5, 'savings_rate': 0.25, 'description': 'Invests regularly, moderate spending'},
            'emi_heavy': {'expense_factor': 0.7, 'savings_rate': 0.05, 'description': 'Multiple EMIs, constrained budget'}
        }
        
    def generate_transactions(self, start_date, end_date, salary_range, profile_type='moderate'):
        """Generate realistic monthly transactions with behavioral patterns"""
        transactions = []
        
        # Get profile
        profile = self.customer_profiles[profile_type]
        expense_factor = profile['expense_factor']
        savings_rate = profile['savings_rate']
        
        # Starting balance correlated with salary
        avg_salary = sum(salary_range) / 2
        current_balance = random.randint(int(avg_salary * 0.3), int(avg_salary * 2))
        
        current_date = start_date
        salary_day = random.choice([1, 25, 28, 30])
        salary = random.randint(*salary_range)
        
        # Define expense categories with realistic patterns
        base_expenses = {
            'Rent Payment': {'min': 8000, 'max': 45000, 'frequency': 'monthly', 'day': random.randint(1, 5)},
            'Electricity Bill': {'min': 800, 'max': 4000, 'frequency': 'monthly', 'day': random.randint(5, 10)},
            'Internet/Mobile Bill': {'min': 500, 'max': 2000, 'frequency': 'monthly', 'day': random.randint(1, 10)},
            'Grocery Store': {'min': 500, 'max': 3000, 'frequency': 'weekly', 'times_per_week': 2},
            'Fuel - Petrol Pump': {'min': 800, 'max': 2500, 'frequency': 'weekly', 'times_per_week': 1},
            'Restaurant/Food': {'min': 200, 'max': 2000, 'frequency': 'random', 'probability': 0.3},
            'Movie/Entertainment': {'min': 300, 'max': 1500, 'frequency': 'random', 'probability': 0.1},
            'Medical/Pharmacy': {'min': 300, 'max': 3000, 'frequency': 'random', 'probability': 0.08},
            'Clothing/Shopping': {'min': 1000, 'max': 5000, 'frequency': 'random', 'probability': 0.12},
        }
        
        # EMIs and credit cards (based on profile)
        if profile_type in ['moderate', 'spender', 'emi_heavy']:
            if profile_type == 'emi_heavy' or random.random() < 0.5:
                base_expenses['EMI - Home Loan'] = {
                    'min': int(salary * 0.25), 'max': int(salary * 0.35), 
                    'frequency': 'monthly', 'day': random.randint(5, 10)
                }
            if random.random() < 0.6:
                base_expenses['EMI - Car Loan'] = {
                    'min': int(salary * 0.10), 'max': int(salary * 0.20), 
                    'frequency': 'monthly', 'day': random.randint(1, 10)
                }
            if random.random() < 0.7:
                base_expenses['Credit Card Payment'] = {
                    'min': int(salary * 0.15), 'max': int(salary * 0.45), 
                    'frequency': 'monthly', 'day': random.randint(10, 20)
                }
        
        # UPI vendors with realistic usage patterns
        upi_vendors = {
            'food_delivery': ['Swiggy', 'Zomato', 'Dunzo'],
            'ecommerce': ['Amazon Pay', 'Flipkart', 'Myntra'],
            'transport': ['Uber', 'Ola', 'Rapido'],
            'grocery': ['BigBasket', 'Blinkit', 'JioMart'],
            'entertainment': ['Netflix', 'Spotify', 'Prime Video', 'Hotstar'],
            'utilities': ['PhonePe Merchant', 'Paytm', 'Google Pay Merchant']
        }
        
        # Track monthly expenses to avoid overspending
        monthly_transactions_done = set()
        
        while current_date <= end_date:
            month_key = current_date.strftime('%Y-%m')
            
            # SALARY CREDIT
            if current_date.day == salary_day:
                ref = f"NEFT{random.randint(100000, 999999)}"
                company = random.choice(self.companies)
                # Add some variation (bonus months, deductions)
                salary_amount = salary
                if random.random() < 0.1:  # 10% chance of bonus
                    salary_amount = int(salary * random.uniform(1.2, 1.5))
                    company += ' (With Bonus)'
                elif random.random() < 0.05:  # 5% chance of deduction
                    salary_amount = int(salary * random.uniform(0.85, 0.95))
                
                transactions.append({
                    'date': current_date.strftime('%d-%b-%Y'),
                    'narration': f'Salary Credit - {company}',
                    'ref': ref,
                    'withdrawal': 0,
                    'deposit': salary_amount,
                    'balance': current_balance + salary_amount
                })
                current_balance += salary_amount
            
            # MONTHLY FIXED EXPENSES
            for category, details in base_expenses.items():
                if details['frequency'] == 'monthly':
                    expense_key = f"{month_key}-{category}"
                    if current_date.day == details['day'] and expense_key not in monthly_transactions_done:
                        amount = random.randint(details['min'], details['max'])
                        amount = int(amount * expense_factor)  # Apply profile factor
                        
                        ref = f"{random.randint(100000, 999999)}"
                        transactions.append({
                            'date': current_date.strftime('%d-%b-%Y'),
                            'narration': category,
                            'ref': ref,
                            'withdrawal': amount,
                            'deposit': 0,
                            'balance': current_balance - amount
                        })
                        current_balance -= amount
                        monthly_transactions_done.add(expense_key)
            
            # WEEKLY EXPENSES (groceries, fuel)
            for category, details in base_expenses.items():
                if details['frequency'] == 'weekly':
                    if current_date.weekday() in [5, 6] and random.random() < (details['times_per_week'] / 2):
                        amount = random.randint(details['min'], details['max'])
                        amount = int(amount * expense_factor)
                        
                        ref = f"{random.randint(100000, 999999)}"
                        transactions.append({
                            'date': current_date.strftime('%d-%b-%Y'),
                            'narration': category,
                            'ref': ref,
                            'withdrawal': amount,
                            'deposit': 0,
                            'balance': current_balance - amount
                        })
                        current_balance -= amount
            
            # RANDOM DAILY EXPENSES
            for category, details in base_expenses.items():
                if details['frequency'] == 'random' and random.random() < details['probability']:
                    amount = random.randint(details['min'], details['max'])
                    amount = int(amount * expense_factor)
                    
                    ref = f"{random.randint(100000, 999999)}"
                    transactions.append({
                        'date': current_date.strftime('%d-%b-%Y'),
                        'narration': category,
                        'ref': ref,
                        'withdrawal': amount,
                        'deposit': 0,
                        'balance': current_balance - amount
                    })
                    current_balance -= amount
            
            # UPI TRANSACTIONS (daily possibility)
            if random.random() < 0.5:  # 50% chance per day
                vendor_category = random.choice(list(upi_vendors.keys()))
                vendor = random.choice(upi_vendors[vendor_category])
                
                # Amount based on category
                if vendor_category == 'food_delivery':
                    amount = random.randint(150, 800)
                elif vendor_category == 'ecommerce':
                    amount = random.randint(500, 5000)
                elif vendor_category == 'transport':
                    amount = random.randint(80, 500)
                elif vendor_category == 'entertainment':
                    amount = random.randint(99, 999)
                else:
                    amount = random.randint(100, 1000)
                
                amount = int(amount * expense_factor)
                ref = f"UPI/{random.randint(100000000, 999999999)}"
                
                transactions.append({
                    'date': current_date.strftime('%d-%b-%Y'),
                    'narration': f'UPI/{vendor}',
                    'ref': ref,
                    'withdrawal': amount,
                    'deposit': 0,
                    'balance': current_balance - amount
                })
                current_balance -= amount
            
            # ATM WITHDRAWALS (less frequent)
            if random.random() < 0.1:
                amount = random.choice([2000, 3000, 5000, 10000])
                ref = f"ATM{random.randint(1000, 9999)}"
                transactions.append({
                    'date': current_date.strftime('%d-%b-%Y'),
                    'narration': 'ATM Cash Withdrawal',
                    'ref': ref,
                    'withdrawal': amount,
                    'deposit': 0,
                    'balance': current_balance - amount
                })
                current_balance -= amount
            
            # INVESTMENTS & SAVINGS (for investor profile)
            if profile_type == 'investor' and current_date.day in [10, 15] and random.random() < 0.3:
                amount = int(salary * random.uniform(0.05, 0.15))
                ref = f"NEFT{random.randint(100000, 999999)}"
                investment_type = random.choice(['Mutual Fund SIP', 'Fixed Deposit', 'Stock Market Transfer', 'PPF Deposit'])
                transactions.append({
                    'date': current_date.strftime('%d-%b-%Y'),
                    'narration': f'Transfer to {investment_type}',
                    'ref': ref,
                    'withdrawal': amount,
                    'deposit': 0,
                    'balance': current_balance - amount
                })
                current_balance -= amount
            
            # DEPOSITS/REFUNDS/INCOME
            if random.random() < 0.08:  # 8% chance
                deposit_type = random.choice([
                    'refund', 'transfer', 'gift', 'freelance', 'bonus', 'tax_refund', 'dividend'
                ])
                
                if deposit_type == 'refund':
                    amount = random.randint(300, 3000)
                    narration = random.choice(['Refund - Online Purchase', 'Refund - Cancelled Order', 'Insurance Claim'])
                elif deposit_type == 'transfer':
                    amount = random.randint(1000, 10000)
                    narration = 'Transfer from Savings'
                elif deposit_type == 'gift':
                    amount = random.randint(2000, 20000)
                    narration = 'Gift Credit'
                elif deposit_type == 'freelance':
                    amount = random.randint(5000, 30000)
                    narration = 'Freelance Income - Project'
                elif deposit_type == 'bonus':
                    amount = random.randint(10000, 50000)
                    narration = 'Annual Bonus Credit'
                elif deposit_type == 'tax_refund':
                    amount = random.randint(5000, 25000)
                    narration = 'Income Tax Refund'
                else:  # dividend
                    amount = random.randint(500, 5000)
                    narration = 'Dividend Credit'
                
                ref = f"NEFT{random.randint(100000, 999999)}"
                transactions.append({
                    'date': current_date.strftime('%d-%b-%Y'),
                    'narration': narration,
                    'ref': ref,
                    'withdrawal': 0,
                    'deposit': amount,
                    'balance': current_balance + amount
                })
                current_balance += amount
            
            # ANOMALIES & EDGE CASES (for fraud detection training)
            if random.random() < 0.02:  # 2% chance of anomaly
                anomaly_type = random.choice(['large_withdrawal', 'bounced_payment', 'suspicious_upi'])
                
                if anomaly_type == 'large_withdrawal':
                    amount = random.randint(50000, 150000)
                    ref = f"CHQ{random.randint(100000, 999999)}"
                    transactions.append({
                        'date': current_date.strftime('%d-%b-%Y'),
                        'narration': 'Large Cheque Withdrawal',
                        'ref': ref,
                        'withdrawal': amount,
                        'deposit': 0,
                        'balance': current_balance - amount
                    })
                    current_balance -= amount
                
                elif anomaly_type == 'bounced_payment':
                    amount = random.randint(5000, 20000)
                    ref = f"CHQ{random.randint(100000, 999999)}"
                    transactions.append({
                        'date': current_date.strftime('%d-%b-%Y'),
                        'narration': 'Cheque Bounce Charges',
                        'ref': ref,
                        'withdrawal': 500,
                        'deposit': 0,
                        'balance': current_balance - 500
                    })
                    current_balance -= 500
                
                elif anomaly_type == 'suspicious_upi':
                    # Multiple small transactions in short time
                    for _ in range(3):
                        amount = random.randint(100, 500)
                        ref = f"UPI/{random.randint(100000000, 999999999)}"
                        transactions.append({
                            'date': current_date.strftime('%d-%b-%Y'),
                            'narration': f'UPI/Unknown Merchant {random.randint(1000, 9999)}',
                            'ref': ref,
                            'withdrawal': amount,
                            'deposit': 0,
                            'balance': current_balance - amount
                        })
                        current_balance -= amount
            
            current_date += timedelta(days=1)
        
        return sorted(transactions, key=lambda x: datetime.strptime(x['date'], '%d-%b-%Y'))
    
    def generate_pdf(self, output_dir='enhanced_bank_statements', count=1000):
        """Generate enhanced bank statement PDFs with metadata"""
        os.makedirs(output_dir, exist_ok=True)
        metadata_file = os.path.join(output_dir, 'metadata.json')
        all_metadata = []
        
        for i in range(count):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 14)
            
            # Bank header
            bank = random.choice(self.banks)
            pdf.cell(0, 10, f'{bank} - Statement of Account', ln=True, align='C')
            pdf.set_font('Arial', '', 9)
            pdf.cell(0, 6, 'We understand your world', ln=True, align='C')
            pdf.ln(5)
            
            # Account details
            pdf.set_font('Arial', '', 9)
            name = random.choice(self.names)
            branch = random.choice(self.branches)
            account_no = f"{random.randint(10000000000, 99999999999)}"
            
            details = [
                f"Account Holder: {name}",
                f"Account Branch: {bank}, {branch}",
                f"Account No.: {account_no}",
                f"IFSC: {bank[:4].upper()}{random.randint(1000, 9999)}",
                f"Account Status: Active"
            ]
            
            for detail in details:
                pdf.cell(0, 5, detail, ln=True)
            
            # Statement period
            end_date = datetime.now() - timedelta(days=random.randint(0, 90))
            start_date = end_date - timedelta(days=random.randint(28, 31))
            pdf.ln(3)
            pdf.set_font('Arial', 'B', 9)
            pdf.cell(0, 5, f"Statement Period: {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}", ln=True)
            pdf.ln(3)
            
            # Table header
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(22, 6, 'Date', 1)
            pdf.cell(70, 6, 'Narration', 1)
            pdf.cell(25, 6, 'Ref No.', 1)
            pdf.cell(25, 6, 'Withdrawal', 1)
            pdf.cell(25, 6, 'Deposit', 1)
            pdf.cell(25, 6, 'Balance', 1)
            pdf.ln()
            
            # Generate transactions with profile
            profile_type = random.choice(list(self.customer_profiles.keys()))
            salary_range = random.choice([
                (30000, 50000), (50000, 75000), (75000, 120000), 
                (120000, 200000), (200000, 400000)
            ])
            
            transactions = self.generate_transactions(start_date, end_date, salary_range, profile_type)
            
            # Calculate summary stats
            total_deposits = sum(t['deposit'] for t in transactions)
            total_withdrawals = sum(t['withdrawal'] for t in transactions)
            net_cashflow = total_deposits - total_withdrawals
            
            # Save metadata
            metadata = {
                'file_id': i + 1,
                'filename': f"statement_{i+1:04d}_{name.replace(' ', '_')}.pdf",
                'account_holder': name,
                'bank': bank,
                'account_number': account_no,
                'period_start': start_date.strftime('%Y-%m-%d'),
                'period_end': end_date.strftime('%Y-%m-%d'),
                'customer_profile': profile_type,
                'profile_description': self.customer_profiles[profile_type]['description'],
                'salary_range': salary_range,
                'total_transactions': len(transactions),
                'total_deposits': total_deposits,
                'total_withdrawals': total_withdrawals,
                'net_cashflow': net_cashflow,
                'opening_balance': transactions[0]['balance'] if transactions else 0,
                'closing_balance': transactions[-1]['balance'] if transactions else 0
            }
            all_metadata.append(metadata)
            
            # Add transactions to PDF (limit to fit on page)
            pdf.set_font('Arial', '', 7)
            for txn in transactions[:40]:  # Increased to 40 transactions
                pdf.cell(22, 5, txn['date'], 1)
                pdf.cell(70, 5, txn['narration'][:35], 1)
                pdf.cell(25, 5, txn['ref'], 1)
                pdf.cell(25, 5, f"Rs.{txn['withdrawal']:,.2f}" if txn['withdrawal'] > 0 else '-', 1)
                pdf.cell(25, 5, f"Rs.{txn['deposit']:,.2f}" if txn['deposit'] > 0 else '-', 1)
                pdf.cell(25, 5, f"Rs.{txn['balance']:,.2f}", 1)
                pdf.ln()
            
            # Footer
            pdf.ln(5)
            pdf.set_font('Arial', 'I', 7)
            pdf.cell(0, 5, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align='C')
            
            # Save PDF
            filename = f"{output_dir}/statement_{i+1:04d}_{name.replace(' ', '_')}.pdf"
            pdf.output(filename)
            
            if (i + 1) % 50 == 0:
                print(f"Generated {i + 1}/{count} statements...")
        
        # Save metadata JSON
        with open(metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)
        
        print(f"\n✅ Successfully generated {count} bank statements in '{output_dir}/' folder")
        print(f"📊 Metadata saved to {metadata_file}")
        print(f"\n📈 Distribution:")
        for profile, details in self.customer_profiles.items():
            count_profile = sum(1 for m in all_metadata if m['customer_profile'] == profile)
            print(f"  - {profile}: {count_profile} ({details['description']})")

# Usage
if __name__ == "__main__":
    generator = EnhancedBankStatementGenerator()
    generator.generate_pdf(
        output_dir='C:/Users/anura/Desktop/FINGPT_MAJOR_PROJECT/data/generators/enhanced_bank_statements', 
        count=1000
    )