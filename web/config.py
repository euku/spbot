"""
Settings of the status page. Every value can be overridden by an environment variable
(used by the tests); the defaults are the Toolforge paths of the tool spbot.
"""
import os

tool_home = os.environ.get('SPBOT_HOME', '/data/project/spbot')
log_dir = os.environ.get('SPBOT_LOG_DIR', os.path.join(tool_home, 'logs'))
repo_dir = os.environ.get('SPBOT_REPO_DIR', os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
jobs_file = os.environ.get('SPBOT_JOBS_FILE', os.path.join(repo_dir, 'jobs', 'toolforge-jobs.yaml'))
venv_dir = os.environ.get('SPBOT_VENV_DIR', os.path.join(tool_home, 'pyvenv'))
replica_cnf = os.environ.get('SPBOT_REPLICA_CNF', os.path.join(tool_home, 'replica.my.cnf'))
# '' switches the replica queries off (tests, local development)
replica_host = os.environ.get('SPBOT_REPLICA_HOST', '{dbname}.analytics.db.svc.wikimedia.cloud')
bot_user = os.environ.get('SPBOT_BOT_USER', 'SpBot')
# how long the replica results are cached (seconds)
replica_cache_seconds = int(os.environ.get('SPBOT_REPLICA_CACHE_SECONDS', '900'))
# how many days of archive summaries a page history looks at
page_history_days = int(os.environ.get('SPBOT_PAGE_HISTORY_DAYS', '7'))
github_url = 'https://github.com/euku/spbot'
