import csv
import os
import random
import json
from datetime import datetime, timedelta

class EnhancedPayslipGenerator:
    def __init__(self):
        self.departments = [
            'IT', 'HR', 'Sales', 'Finance', 'Operations', 
            'Marketing', 'Customer Service', 'Legal', 'Product', 'Data Science'
        ]
        
        self.designations = {
            'IT': ['Junior Developer', 'Software Engineer', 'Senior Engineer', 'Tech Lead', 'Engineering Manager', 'Architect', 'VP Engineering'],
            'HR': ['HR Executive', 'HR Manager', 'Recruiter', 'HR Business Partner', 'Talent Acquisition Lead', 'HRBP Manager'],
            'Sales': ['Sales Executive', 'Sales Manager', 'Business Development Manager', 'Regional Manager', 'Sales Director', 'VP Sales'],
            'Finance': ['Junior Accountant', 'Accountant', 'Finance Analyst', 'Senior Analyst', 'Finance Manager', 'Controller', 'CFO'],
            'Operations': ['Operations Executive', 'Operations Manager', 'Process Lead', 'Operations Director'],
            'Marketing': ['Marketing Executive', 'Marketing Manager', 'Brand Manager', 'Digital Marketing Manager', 'Marketing Director', 'CMO'],
            'Customer Service': ['Support Executive', 'Customer Support Lead', 'Team Lead', 'Service Manager', 'Head of Support'],
            'Legal': ['Legal Associate', 'Legal Manager', 'Senior Counsel', 'General Counsel'],
            'Product': ['Associate Product Manager', 'Product Manager', 'Senior PM', 'Group PM', 'VP Product'],
            'Data Science': ['Data Analyst', 'Data Scientist', 'Senior Data Scientist', 'ML Engineer', 'Head of Data Science']
        }
        
        # More granular salary ranges by designation level and seniority
        self.salary_ranges = {
            'Junior': (30000, 50000),
            'Executive': (35000, 60000),
            'Associate': (40000, 65000),
            'Analyst': (45000, 75000),
            'Developer': (45000, 75000),
            'Engineer': (50000, 85000),
            'Manager': (80000, 150000),
            'Senior': (70000, 120000),
            'Lead': (90000, 140000),
            'Architect': (150000, 250000),
            'Director': (180000, 300000),
            'VP': (250000, 450000),
            'Head': (200000, 350000),
            'CFO': (400000, 700000),
            'CMO': (350000, 600000),
            'CTO': (400000, 700000),
            'Counsel': (150000, 280000),
            'Partner': (180000, 320000)
        }
        
        self.first_names = [
            'Rahul', 'Priya', 'Amit', 'Sneha', 'Vikram', 'Anjali', 'Rohan', 'Kavya',
            'Arjun', 'Pooja', 'Karan', 'Divya', 'Nikhil', 'Ritu', 'Sanjay', 'Neha',
            'Aditya', 'Megha', 'Varun', 'Shruti', 'Kunal', 'Isha', 'Siddharth', 'Ananya',
            'Rajesh', 'Meera', 'Vishal', 'Tanvi', 'Abhishek', 'Nidhi', 'Gaurav', 'Simran'
        ]
        
        self.last_names = [
            'Sharma', 'Patel', 'Kumar', 'Reddy', 'Singh', 'Gupta', 'Mehta', 'Iyer',
            'Nair', 'Joshi', 'Shah', 'Verma', 'Desai', 'Malhotra', 'Kapoor', 'Chopra',
            'Agarwal', 'Bansal', 'Khanna', 'Pillai', 'Roy', 'Rao', 'Sinha', 'Mishra'
        ]
        
        # Cities with cost of living index (affects HRA)
        self.cities = {
            'Mumbai': 1.3,
            'Bengaluru': 1.2,
            'Delhi': 1.25,
            'Hyderabad': 1.0,
            'Chennai': 1.0,
            'Pune': 1.1,
            'Kolkata': 0.9,
            'Ahmedabad': 0.85
        }
        
        # Employee status types
        self.employment_types = ['Full-Time', 'Contract', 'Intern', 'Part-Time']
        
    def get_salary_for_designation(self, designation):
        """Get appropriate salary range based on designation with variations"""
        for level, (min_sal, max_sal) in self.salary_ranges.items():
            if level.lower() in designation.lower():
                # Add ±10% variation for market differences
                base = random.randint(min_sal, max_sal)
                variation = random.uniform(-0.1, 0.1)
                return int(base * (1 + variation))
        # Default range for unmatched
        return random.randint(40000, 70000)
    
    def calculate_components(self, basic_pay, city='Bengaluru', employment_type='Full-Time', 
                           days_worked=26, has_variable_pay=False, performance_rating='Good'):
        """Calculate all salary components with realistic variations"""
        
        # City-based HRA adjustment
        city_multiplier = self.cities.get(city, 1.0)
        
        # HRA calculation (40-50% of basic, adjusted by city)
        hra_percentage = random.uniform(0.40, 0.50)
        hra = int(basic_pay * hra_percentage * city_multiplier)
        
        # Special allowance (10-20% of basic)
        special_allowance = int(basic_pay * random.uniform(0.10, 0.20))
        
        # Transport allowance (capped, partially exempt)
        transport_allowance = random.randint(1600, 3200)
        
        # Medical allowance (capped at 15000/year = 1250/month)
        medical_allowance = random.randint(1250, 2500)
        
        # Variable pay (for sales, senior roles)
        variable_pay = 0
        if has_variable_pay:
            if performance_rating == 'Excellent':
                variable_pay = int(basic_pay * random.uniform(0.15, 0.30))
            elif performance_rating == 'Good':
                variable_pay = int(basic_pay * random.uniform(0.08, 0.15))
            elif performance_rating == 'Average':
                variable_pay = int(basic_pay * random.uniform(0.03, 0.08))
        
        # Bonus (quarterly/annual - 10% chance)
        bonus = 0
        if random.random() < 0.1:
            bonus = int(basic_pay * random.uniform(0.10, 0.50))
        
        # Leave encashment (rare)
        leave_encashment = 0
        if random.random() < 0.05:
            leave_encashment = int(basic_pay * random.uniform(0.05, 0.15))
        
        # Overtime (for lower-level employees)
        overtime = 0
        if basic_pay < 60000 and random.random() < 0.15:
            overtime = random.randint(2000, 8000)
        
        # Gross earnings
        gross_earnings = (basic_pay + hra + special_allowance + transport_allowance + 
                         medical_allowance + variable_pay + bonus + leave_encashment + overtime)
        
        # Pro-rate for partial months
        if days_worked < 26:
            proration_factor = days_worked / 26
            basic_pay = int(basic_pay * proration_factor)
            hra = int(hra * proration_factor)
            special_allowance = int(special_allowance * proration_factor)
            gross_earnings = int(gross_earnings * proration_factor)
        
        # DEDUCTIONS
        
        # PF (12% of basic, capped at 1800 if basic > 15000)
        if employment_type in ['Full-Time', 'Contract']:
            pf = min(int(basic_pay * 0.12), 1800) if basic_pay > 15000 else int(basic_pay * 0.12)
        else:
            pf = 0  # No PF for interns/part-time
        
        # Professional tax (state-dependent, simplified)
        if gross_earnings > 21000:
            professional_tax = 200
        elif gross_earnings > 15000:
            professional_tax = 150
        else:
            professional_tax = 0
        
        # TDS calculation (progressive tax slabs)
        annual_income = gross_earnings * 12
        if employment_type == 'Intern':
            tds = 0  # Interns usually below taxable limit
        else:
            if annual_income <= 250000:
                tds = 0
            elif annual_income <= 500000:
                tds = int((annual_income - 250000) * 0.05 / 12)
            elif annual_income <= 750000:
                tds = int((12500 + (annual_income - 500000) * 0.10) / 12)
            elif annual_income <= 1000000:
                tds = int((37500 + (annual_income - 750000) * 0.15) / 12)
            elif annual_income <= 1250000:
                tds = int((75000 + (annual_income - 1000000) * 0.20) / 12)
            elif annual_income <= 1500000:
                tds = int((125000 + (annual_income - 1250000) * 0.25) / 12)
            else:
                tds = int((187500 + (annual_income - 1500000) * 0.30) / 12)
        
        # Health insurance (optional, employer-provided)
        insurance = 0
        if random.random() < 0.6:  # 60% have insurance
            insurance = random.choice([0, 500, 1000, 1500, 2000])
        
        # Loan deductions (20% of employees)
        loan_deduction = 0
        if random.random() < 0.2:
            loan_deduction = random.choice([3000, 5000, 8000, 10000, 15000])
        
        # Advance salary deduction (rare, 5%)
        advance_deduction = 0
        if random.random() < 0.05:
            advance_deduction = random.randint(5000, 20000)
        
        # Miscellaneous deductions (canteen, notice period recovery, etc.)
        misc_deduction = 0
        if random.random() < 0.1:
            misc_types = ['Canteen', 'Notice Period Recovery', 'Other']
            misc_deduction = random.randint(500, 3000)
        
        total_deductions = (pf + professional_tax + tds + insurance + 
                           loan_deduction + advance_deduction + misc_deduction)
        
        net_pay = gross_earnings - total_deductions
        
        return {
            'Basic_Pay': basic_pay,
            'HRA': hra,
            'Special_Allowance': special_allowance,
            'Transport_Allowance': transport_allowance,
            'Medical_Allowance': medical_allowance,
            'Variable_Pay': variable_pay,
            'Bonus': bonus,
            'Leave_Encashment': leave_encashment,
            'Overtime': overtime,
            'Gross_Earnings': gross_earnings,
            'PF': pf,
            'Professional_Tax': professional_tax,
            'TDS': tds,
            'Insurance': insurance,
            'Loan_Deduction': loan_deduction,
            'Advance_Deduction': advance_deduction,
            'Misc_Deduction': misc_deduction,
            'Total_Deductions': total_deductions,
            'Net_Pay': net_pay,
            'City': city,
            'Employment_Type': employment_type
        }
    
    def generate_payslips(self, output_file='enhanced_payslips.csv', count=1000):
        """Generate realistic payslip CSV with diverse scenarios"""
        
        fieldnames = [
            'Employee_ID', 'Employee_Name', 'Department', 'Designation',
            'City', 'Employment_Type', 'Days_Worked', 'Basic_Pay', 'HRA', 
            'Special_Allowance', 'Transport_Allowance', 'Medical_Allowance',
            'Variable_Pay', 'Bonus', 'Leave_Encashment', 'Overtime',
            'Gross_Earnings', 'PF', 'Professional_Tax', 'TDS',
            'Insurance', 'Loan_Deduction', 'Advance_Deduction', 'Misc_Deduction',
            'Total_Deductions', 'Net_Pay', 'Month', 'Year'
        ]
        
        metadata = []
        
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for i in range(1, count + 1):
                # Employee details
                emp_id = f"EMP{i:04d}"
                name = f"{random.choice(self.first_names)} {random.choice(self.last_names)}"
                department = random.choice(self.departments)
                designation = random.choice(self.designations[department])
                city = random.choice(list(self.cities.keys()))
                
                # Employment type (90% full-time, 7% contract, 2% intern, 1% part-time)
                employment_type = random.choices(
                    self.employment_types,
                    weights=[90, 7, 2, 1]
                )[0]
                
                # Work days (22-31 days, with occasional partial months)
                if random.random() < 0.15:  # 15% have partial months (new joiners, resignations)
                    days_worked = random.randint(10, 25)
                else:
                    days_worked = random.randint(24, 26)  # Normal full month
                
                # Calculate salary
                monthly_basic = self.get_salary_for_designation(designation)
                
                # Adjust for employment type
                if employment_type == 'Intern':
                    monthly_basic = random.randint(15000, 35000)
                elif employment_type == 'Part-Time':
                    monthly_basic = int(monthly_basic * 0.6)
                elif employment_type == 'Contract':
                    monthly_basic = int(monthly_basic * 1.1)  # Slightly higher for contractors
                
                # Variable pay eligibility (Sales, senior roles)
                has_variable_pay = (department == 'Sales' or 
                                   any(level in designation for level in ['Manager', 'Director', 'VP', 'Lead']))
                
                performance_rating = random.choices(
                    ['Excellent', 'Good', 'Average', 'Below Average'],
                    weights=[15, 60, 20, 5]
                )[0]
                
                components = self.calculate_components(
                    monthly_basic, 
                    city=city,
                    employment_type=employment_type,
                    days_worked=days_worked,
                    has_variable_pay=has_variable_pay,
                    performance_rating=performance_rating
                )
                
                # Month/Year (vary across recent months)
                months_back = random.randint(0, 6)
                date = datetime.now() - timedelta(days=months_back * 30)
                month = date.strftime('%B')
                year = date.year
                
                row = {
                    'Employee_ID': emp_id,
                    'Employee_Name': name,
                    'Department': department,
                    'Designation': designation,
                    'City': city,
                    'Employment_Type': employment_type,
                    'Days_Worked': days_worked,
                    'Month': month,
                    'Year': year,
                    **components
                }
                
                writer.writerow(row)
                
                # Track metadata
                metadata.append({
                    'employee_id': emp_id,
                    'name': name,
                    'department': department,
                    'designation': designation,
                    'city': city,
                    'employment_type': employment_type,
                    'performance_rating': performance_rating,
                    'gross_earnings': components['Gross_Earnings'],
                    'net_pay': components['Net_Pay'],
                    'deduction_percentage': round((components['Total_Deductions'] / components['Gross_Earnings']) * 100, 2) if components['Gross_Earnings'] > 0 else 0
                })
                
                if (i) % 100 == 0:
                    print(f"Generated {i}/{count} payslips...")
        
        # Save metadata
        metadata_file = output_file.replace('.csv', '_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✅ Successfully generated {count} payslips in '{output_file}'")
        print(f"📊 Metadata saved to {metadata_file}")
        
        # Print summary statistics
        print("\n📈 Summary Statistics:")
        print(f"Departments: {', '.join(self.departments)}")
        print(f"Cities: {', '.join(self.cities.keys())}")
        print(f"Salary Range: ₹15,000 - ₹7,00,000")
        
        # Calculate and display distributions
        emp_type_dist = {}
        dept_dist = {}
        for m in metadata:
            emp_type_dist[m['employment_type']] = emp_type_dist.get(m['employment_type'], 0) + 1
            dept_dist[m['department']] = dept_dist.get(m['department'], 0) + 1
        
        print("\n📊 Employment Type Distribution:")
        for emp_type, count in emp_type_dist.items():
            print(f"  - {emp_type}: {count} ({count/len(metadata)*100:.1f}%)")
        
        print("\n📊 Department Distribution:")
        for dept, count in sorted(dept_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {dept}: {count} ({count/len(metadata)*100:.1f}%)")
        
        # Calculate average deduction percentage
        avg_deduction = sum(m['deduction_percentage'] for m in metadata) / len(metadata)
        print(f"\n💰 Average Deduction: {avg_deduction:.2f}% of gross")

# Usage
if __name__ == "__main__":
    generator = EnhancedPayslipGenerator()
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(current_dir, 'enhanced_payslips.csv')
    
    generator.generate_payslips(output_file=output_path, count=1000)