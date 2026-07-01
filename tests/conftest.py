from dotenv import load_dotenv

# Load .env so the Pipelex API client picks up PIPELEX_API_URL / PIPELEX_API_KEY
# (the tests marked `pipelex_api` / `inference` reach the hosted API).
load_dotenv()
