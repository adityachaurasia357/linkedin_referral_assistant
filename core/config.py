"""
User-editable configuration.

Everything a non-developer needs to change before running the tool
lives in this file, so the rest of the codebase never has to be touched.
"""

# Path to your LinkedIn "Connections.csv" export. See README.md for
# how to download it.
CONNECTIONS_FILE = r"C:\Users\yourname\Downloads\connections.csv"

# Folder used as a DEDICATED, PERSISTENT Chrome profile. LinkedIn
# session/cookies live here after your first manual login, so you
# won't have to log in again on future runs. Use a folder that isn't
# your everyday Chrome profile.
CHROME_PROFILE_DIR = r"C:\LinkedInReferralAssistant\ChromeProfile"

# Where processed-connection history is kept. Safe to keep across runs.
SENT_LOG_FILE = "sent_log.csv"

# How long to wait (seconds) after navigating to a profile page for
# it to finish loading before showing it to you.
PAGE_LOAD_WAIT_SECONDS = 2.5

# Personalized message template. Supported placeholders:
#   {name}        full name, e.g. "Rahul Sharma"
#   {first_name}  e.g. "Rahul"
#   {last_name}   e.g. "Sharma"
#   {company}     current company if known, else a generic fallback
#   {position}    current position/title if known, else a generic fallback
MESSAGE_TEMPLATE = """Hi {first_name},

Hope you're doing well! I'm currently exploring software
engineering opportunities and noticed that {company} has
some relevant openings.

Would you be comfortable referring me for a suitable role?
I'd really appreciate your help.

Thanks!
"""

# Used in the message when a connection's CSV row has no company/position.
DEFAULT_COMPANY_TEXT = "your company"
DEFAULT_POSITION_TEXT = "your role"
