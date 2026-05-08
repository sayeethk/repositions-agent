# Process ISC Agent CSV download and update project priorities.
# Usage: python scripts/process_isc_csv.py <path_to_csv_file>

import csv
import sys
import os
import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.excel_loader import ExcelLoader
from data.models import Project, parse_date, Status
from core.agent import RepositionsAgent
from utils.helpers import (
    format_date,
    format_currency,
    days_remaining,
    status_icon,
    priority_label,
    print_separator,
    print_boxed_header,
)


def process_csv(csv_path: str):
    """Load CSV from ISC Agent and update projects."""
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV file not found: {csv_path}")
        return
    
    print(f"\n[ISC] Processing CSV: {csv_path}")
    
    # Load CSV data
    csv_data = {}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"  [OK] Loaded {len(rows)} rows from CSV")
        
        for row in rows:
            # Try different column name formats
            part_num = None
            for col in ['Part', 'part_number', 'Part Number', 'PartNumber']:
                if col in row and row[col]:
                    part_num = row[col].strip()
                    break
            
            if not part_num:
                continue
            
            # Get line-down date
            line_down = None
            for col in ['Linedown Date', 'linedown_date', 'Line-Down Date', 'RequestedDeliveryDate', 'Requested Delivery Date']:
                if col in row and row[col] and row[col].strip() not in ('N/A', '', 'None'):
                    line_down = row[col].strip()
                    break
            
            # Get revenue impact
            revenue = 0.0
            for col in ['Revenue Impact (USD)', 'revenue_impact', 'Revenue Impact', 'OpenValueUSD', 'OrderValue']:
                if col in row and row[col]:
                    rev_str = row[col].strip().replace('$', '').replace(',', '')
                    try:
                        revenue = float(rev_str)
                    except ValueError:
                        revenue = 0.0
                    break
            
            # Get customer name
            customer = None
            for col in ['Customer Name', 'customer_name', 'Customer', 'CustomerCode']:
                if col in row and row[col]:
                    customer = row[col].strip()
                    break
            
            # Get open PO qty
            open_qty = 0.0
            for col in ['Open PO Qty', 'open_po_qty', 'OpenQuantity', 'Open Qty']:
                if col in row and row[col]:
                    qty_str = row[col].strip().replace(',', '')
                    try:
                        open_qty = float(qty_str)
                    except ValueError:
                        open_qty = 0.0
                    break
            
            # Aggregate by part number
            if part_num in csv_data:
                existing = csv_data[part_num]
                existing['revenue_impact'] += revenue
                existing['open_qty'] += open_qty
                if line_down and (not existing['line_down_date'] or line_down < existing['line_down_date']):
                    existing['line_down_date'] = line_down
                # Keep all customers
                if customer and customer not in existing['customers']:
                    existing['customers'].append(customer)
            else:
                csv_data[part_num] = {
                    'line_down_date': line_down,
                    'revenue_impact': revenue,
                    'open_qty': open_qty,
                    'customers': [customer] if customer else [],
                }
    
    print(f"  [OK] Aggregated {len(csv_data)} unique parts")
    
    # Load projects from Excel
    print("\n[ISC] Loading projects from Excel...")
    loader = ExcelLoader()
    projects_dict = loader.load_projects()
    
    # Initialize agent
    agent = RepositionsAgent()
    agent.load_projects(projects_dict)
    
    # Enrich with CSV data
    enriched_count = 0
    for part_num, data in csv_data.items():
        if part_num in projects_dict:
            proj = projects_dict[part_num]
            if data['line_down_date']:
                parsed_date = parse_date(data['line_down_date'])
                proj.line_down_date = parsed_date
            proj.revenue_impact_daily = data['revenue_impact']
            print(f"  [OK] {part_num}: line_down={data['line_down_date'] or 'N/A'}, revenue=${data['revenue_impact']:,.2f}, qty={data['open_qty']:.0f}")
            enriched_count += 1
    
    print(f"\n[OK] Enriched {enriched_count}/{len(projects_dict)} projects with ISC data")
    
    # Recalculate priorities
    agent.recalculate_all()
    
    # Display top risks
    print("\n" + "=" * 60)
    print("           UPDATED DASHBOARD: TOP RISK PROJECTS")
    print("=" * 60)
    
    top_risks = agent.get_top_risks(limit=10)
    for i, proj in enumerate(top_risks, 1):
        icon = status_icon(proj.status)
        label = priority_label(proj.priority_score)
        days = days_remaining(proj.line_down_date) if proj.line_down_date else 0
        
        print(f"\n  {i}. {icon} {proj.name} (Part: {proj.part_number})")
        print(f"     Status: {proj.status.value} | Priority: {label} ({proj.priority_score:.1f})")
        
        if proj.line_down_date:
            print(f"     Line-Down: {format_date(proj.line_down_date)} ({days} days left)")
        else:
            print(f"     Line-Down: No line-down date")
        
        print(f"     Revenue: ${proj.revenue_impact_daily:,.2f}/day")
        
        overdue = [m for m in proj.milestones.values() if m.is_overdue]
        if overdue:
            print(f"     [!!] {len(overdue)} overdue milestone(s)")
        else:
            print(f"     [OK] No overdue milestones")
    
    print_separator("-")
    print("\n[OK] Priority list updated with ISC data.")
    print("  Run 'python main.py' for interactive dashboard.\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/process_isc_csv.py <path_to_csv_file>")
        print("\nExample:")
        print('  python scripts/process_isc_csv.py "C:\\Users\\H525267\\Downloads\\query_result.csv"')
        print("\nOr check recent CSV files:")
        downloads = os.path.expanduser("~/Downloads")
        if os.path.exists(downloads):
            csv_files = [f for f in os.listdir(downloads) if f.endswith('.csv')]
            if csv_files:
                csv_files.sort(key=lambda f: os.path.getmtime(os.path.join(downloads, f)), reverse=True)
                print("  Recent CSV files in Downloads:")
                for f in csv_files[:5]:
                    path = os.path.join(downloads, f)
                    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
                    print(f"    {mtime:%Y-%m-%d %H:%M} - {f}")
        return
    
    csv_path = sys.argv[1]
    process_csv(csv_path)


if __name__ == "__main__":
    main()
