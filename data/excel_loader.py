import openpyxl
from data.models import Project, Milestone
from config.settings import EXCEL_PATH

def load_projects(self):
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
    sheet = wb['SIMS_Template']

    # ✅ MUST be inside function
    header_row = 26

    headers = [sheet.cell(header_row, c).value for c in range(1, sheet.max_column + 1)]

    projects = {}

    for row in range(header_row + 1, sheet.max_row + 1):
        if not sheet.cell(row, 1).value:
            continue

        row_data = {}
        for col in range(1, sheet.max_column + 1):
            header = headers[col - 1]
            if header:
                row_data[header] = sheet.cell(row, col).value

        name = row_data.get("Project Name")
        part_number = row_data.get("Part Number")

        if not name or not part_number:
            continue

        metadata = {
            "part_number": part_number,
            "line_down_date": row_data.get("Line Down Date"),
            "revenue": row_data.get("Revenue Impact Per Day", 0)
        }

        milestones = {}
        for key, value in row_data.items():
            if "Baseline ECD" in str(key):
                m_name = key.replace(" Baseline ECD", "")
                m = Milestone(m_name)
                m.baseline = value
                milestones[m_name] = m

        projects[name] = Project(name, metadata, milestones)

    return projects