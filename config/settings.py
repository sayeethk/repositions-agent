EXCEL_PATH = "C:/Users/H525267/Projects/repositions-agent/input/Simplified IMS Template - Maricopa.xlsm"
DEPENDENCIES_PATH = "./config/milestone_dependencies.json"

# ISC Agent Configuration
ISC_AGENT_URL = "https://planning.honeywell.com/ISCAgent/"
ISC_REQUEST_TEMPLATE = {
    "part_numbers": "{{PARTS}}"
}
ISC_RESPONSE_FIELDS = {
    "part_number": "part_number",
    "line_down_date": "line_down_date",
    "revenue_impact": "revenue_impact"
}
ISC_TIMEOUT_SECONDS = 30
ISC_MAX_RETRIES = 3
ISC_VERIFY_SSL = False