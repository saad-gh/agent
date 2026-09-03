"""
Workflow Agent Django project settings.
Consumes workflow_orchestrator and provides agentic workflow building capabilities.
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'workflow-agent-dev-secret-key-change-in-prod')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Database Configuration (Postgres with pgvector)
# ---------------------------------------------------------------------------
DB_USER = os.environ.get('DB_USER', 'feature')
DB_PASS = os.environ.get('DB_PASS', '')
DB_NAME = os.environ.get('DB_NAME', 'signup_testing')
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = os.environ.get('DB_PORT', '5432')

if os.environ.get('USE_SQLITE', 'False').lower() in ('true', '1', 'yes'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASS,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
        }
    }

# ---------------------------------------------------------------------------
# Redis / RQ Configuration
# ---------------------------------------------------------------------------
REDIS_HOST = os.environ.get('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
REDIS_DB = int(os.environ.get('REDIS_DB', 0))
REDIS_AUTH = os.environ.get('REDIS_AUTH') or None

_rq_config = {
    'HOST': REDIS_HOST,
    'PORT': REDIS_PORT,
    'DB': REDIS_DB,
    'DEFAULT_TIMEOUT': 3600,
}
if REDIS_AUTH:
    _rq_config['PASSWORD'] = REDIS_AUTH

RQ_QUEUES = {
    'high': _rq_config,
    'default': _rq_config,
    'low': _rq_config,
}

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_rq',
    'workflow_orchestrator',
    'workflow_agent',
]

ROOT_URLCONF = 'workflow_agent.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ---------------------------------------------------------------------------
# workflow_orchestrator extensions & swappable models
# ---------------------------------------------------------------------------
TASK_EXECUTORS = {
    'llm': 'workflow_agent.executors.LLMExecutor',
    'generated_python': 'workflow_agent.executors.GeneratedPythonExecutor',
}

TASK_JINJA_HELPERS_LOADER = 'workflow_agent.helpers.load_approved_helpers'

TASK_ORGANIZATION_MODEL = os.environ.get('TASK_ORGANIZATION_MODEL', 'workflow_orchestrator.Organization')
TASK_SERVICE_MODEL = os.environ.get('TASK_SERVICE_MODEL', 'workflow_orchestrator.Service')
TASK_RESOURCE_MODEL = os.environ.get('TASK_RESOURCE_MODEL', 'workflow_orchestrator.Resource')
TASK_CREDENTIAL_MODEL = os.environ.get('TASK_CREDENTIAL_MODEL', 'workflow_orchestrator.Credential')

# ---------------------------------------------------------------------------
# Agent Configuration Placeholders
# ---------------------------------------------------------------------------
LLM_DEFAULT_PROVIDER = os.environ.get('LLM_DEFAULT_PROVIDER', 'openai')
LLM_DEFAULT_MODEL = os.environ.get('LLM_DEFAULT_MODEL', 'gpt-4o')

SEARCH_PROVIDER_PRIMARY = os.environ.get('SEARCH_PROVIDER_PRIMARY', 'tavily')
SEARCH_PROVIDER_SECONDARY = os.environ.get('SEARCH_PROVIDER_SECONDARY', 'google')

VECTOR_DIMENSIONS = int(os.environ.get('VECTOR_DIMENSIONS', 1536))
EMBEDDING_MODEL_RESOURCE_ID = os.environ.get('EMBEDDING_MODEL_RESOURCE_ID', None)

# ---------------------------------------------------------------------------
# i18n / static
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
