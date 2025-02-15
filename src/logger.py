import logging
import os
from datetime import datetime

def get_logger(source_file):
    # Get filename without extension
    base_filename = os.path.splitext(os.path.basename(source_file))[0]
    
    # Get backend directory path
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(backend_dir, 'logs')
    
    # Create logs directory if it doesn't exist
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Create log filename with timestamp and source filename
    log_filename = os.path.join(logs_dir, f'{base_filename}_{timestamp}.log')
    
    # Create a logger object
    logger = logging.getLogger(f'{base_filename}_{timestamp}')
    logger.setLevel(logging.DEBUG)
    
    # Create file handler
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    return logger

# Example usage
if __name__ == "__main__":
    logger = get_logger(__file__)
    logger.info("This is a test message")
