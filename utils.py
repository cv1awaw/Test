# utils.py

import sqlite3
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

DATABASE = 'warnings.db'

def group_exists(group_id):
    """
    Check if a group exists in the database.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
        exists = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked existence of group {group_id}: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking group existence for {group_id}: {e}")
        return False

def set_group_sad(group_id, is_sad):
    """
    Enable or disable message deletion for a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Assuming there's a column 'is_sad' in the 'groups' table
        c.execute('ALTER TABLE groups ADD COLUMN is_sad BOOLEAN DEFAULT FALSE')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    except Exception as e:
        logger.error(f"Error altering groups table: {e}")
        raise

    try:
        c.execute('UPDATE groups SET is_sad = ? WHERE group_id = ?', (is_sad, group_id))
        conn.commit()
        conn.close()
        logger.info(f"Set is_sad={is_sad} for group {group_id}")
    except Exception as e:
        logger.error(f"Error setting is_sad for group {group_id}: {e}")
        raise

def is_global_tara(user_id):
    """
    Check if a user is a global TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a global TARA: {e}")
        return False

def is_normal_tara(user_id):
    """
    Check if a user is a normal TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a normal TARA: {e}")
        return False
