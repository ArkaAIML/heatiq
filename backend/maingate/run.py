import uvicorn
import logging
import sys

# Configure logging for observability
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def main():
    logger.info("=========================================")
    logger.info(" HEATIQ MAIN GATE - SERVER STARTUP       ")
    logger.info("=========================================")
    logger.info("Environment: Development")
    logger.info("Listening on: http://127.0.0.1:8000")
    logger.info("Dashboard available at: http://127.0.0.1:8000/")
    logger.info("API Docs available at: http://127.0.0.1:8000/docs")
    logger.info("Stores Initialized: SQLite (Keys), Wire 1 DB, Wire 2 Context")
    logger.info("=========================================")
    
    uvicorn.run("backend.maingate.app:app", host="127.0.0.1", port=8000, log_level="warning")

if __name__ == "__main__":
    main()
