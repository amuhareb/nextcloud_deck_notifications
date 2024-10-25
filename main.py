import os
from dotenv import load_dotenv
import mysql.connector
import smtplib
from email.mime.text import MIMEText
import logging
from typing import Dict, Optional

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    filename='assignment_notifications.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Database configuration
db_config = {
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_DATABASE'),
}

# Table configuration
DB_PREFIX = os.getenv('DB_PREFIX', '')  # e.g., 'nc_'
DECK_CARDS_TABLE = f'{DB_PREFIX}deck_cards'
DECK_STACKS_TABLE = f'{DB_PREFIX}deck_stacks'
DECK_BOARDS_TABLE = f'{DB_PREFIX}deck_boards'
DECK_ASSIGNMENTS_TABLE = f'{DB_PREFIX}deck_assigned_users'
USER_TABLE = f'{DB_PREFIX}users'
NOTIFICATION_TABLE = 'assignment_notifications'

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM')
NEXTCLOUD_URL = os.getenv('NEXTCLOUD_URL', 'https://cloud.yourdomain.com')

class DatabaseConnection:
    def __init__(self):
        self.connection = None
        self.cursor = None

    def __enter__(self):
        self.connection = mysql.connector.connect(**db_config)
        self.cursor = self.connection.cursor(dictionary=True)
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.connection.rollback()
        else:
            self.connection.commit()
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()

def send_email(to_address: str, subject: str, body: str) -> None:
    """Send an email using configured SMTP settings."""
    logging.info(f'Sending email to {to_address}')
    
    # Remove any leading/trailing whitespace from the HTML body
    body = body.strip()
    
    # Create message with explicit encoding
    msg = MIMEText(body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = to_address

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.send_message(msg)
        logging.info('Email sent successfully.')
    except Exception as e:
        logging.error(f'Failed to send email to {to_address}: {e}')
        raise

def get_user_emails() -> Dict[str, str]:
    """Fetch all user email mappings from the database."""
    with DatabaseConnection() as cursor:
        query = f"""
        SELECT u.uid, p.configvalue as email
        FROM {USER_TABLE} u
        JOIN {DB_PREFIX}preferences p ON u.uid = p.userid
        WHERE p.appid = 'settings'
        AND p.configkey = 'email'
        AND p.configvalue != ''
        """
        cursor.execute(query)
        results = cursor.fetchall()
        # Decode bytes to strings if necessary
        return {
            row['uid']: row['email'].decode('utf-8') if isinstance(row['email'], bytes) else row['email']
            for row in results
        }

def get_card_details(card_id: int) -> Optional[Dict[str, str]]:
    """Fetch card details including board and stack information."""
    with DatabaseConnection() as cursor:
        query = f"""
        SELECT 
            c.title,
            c.description,
            b.title AS board_title,
            s.title AS stack_title,
            b.id AS board_id
        FROM {DECK_CARDS_TABLE} c
        JOIN {DECK_STACKS_TABLE} s ON c.stack_id = s.id
        JOIN {DECK_BOARDS_TABLE} b ON s.board_id = b.id
        WHERE c.id = %s
        """
        cursor.execute(query, (card_id,))
        result = cursor.fetchone()
        
        if not result:
            logging.warning(f'No card found with ID {card_id}')
            return None
            
        return {
            'title': result['title'],
            'description': result['description'],
            'board_title': result['board_title'],
            'stack_title': result['stack_title'],
            'board_id': result['board_id']
        }

def initialize_notification_table() -> None:
    """Create the notification tracking table if it doesn't exist."""
    with DatabaseConnection() as cursor:
        # First create the table if it doesn't exist
        query = f"""
        CREATE TABLE IF NOT EXISTS {NOTIFICATION_TABLE} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            card_id INT NOT NULL,
            participant VARCHAR(255) NOT NULL,
            notified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_assignment (card_id, participant)
        )
        """
        cursor.execute(query)
        
        # Check if this is first run (table is empty)
        cursor.execute(f"SELECT COUNT(*) as count FROM {NOTIFICATION_TABLE}")
        result = cursor.fetchone()
        
        # If table is empty, mark all existing assignments as notified
        if result['count'] == 0:
            query = f"""
            INSERT INTO {NOTIFICATION_TABLE} (card_id, participant, notified)
            SELECT card_id, participant, TRUE
            FROM {DECK_ASSIGNMENTS_TABLE}
            """
            cursor.execute(query)
            logging.info("Marked all existing assignments as notified")

def sync_assignments() -> None:
    """Sync only new assignments from deck_assigned_users to our notification table."""
    with DatabaseConnection() as cursor:
        # Insert only assignments that don't exist in our notification table
        query = f"""
        INSERT IGNORE INTO {NOTIFICATION_TABLE} (card_id, participant, notified)
        SELECT a.card_id, a.participant, FALSE
        FROM {DECK_ASSIGNMENTS_TABLE} a
        LEFT JOIN {NOTIFICATION_TABLE} n 
            ON a.card_id = n.card_id 
            AND a.participant = n.participant
        WHERE n.id IS NULL
        """
        cursor.execute(query)

def process_notifications() -> None:
    """Process all unnotified assignments and send emails."""
    initialize_notification_table()
    sync_assignments()
    user_emails = get_user_emails()

    with DatabaseConnection() as cursor:
        cursor.execute(f"SELECT * FROM {NOTIFICATION_TABLE} WHERE notified = 0")
        notifications = cursor.fetchall()

        for notification in notifications:
            card_id = notification['card_id']
            uid = notification['participant']
            to_address = user_emails.get(uid)

            if not to_address:
                logging.warning(f'No email found for user {uid}')
                continue

            # Ensure uid is string
            uid = uid.decode('utf-8') if isinstance(uid, bytes) else uid
            
            card_details = get_card_details(card_id)
            if not card_details:
                continue

            # Ensure all card details are strings
            card_details = {
                k: v.decode('utf-8') if isinstance(v, bytes) else v
                for k, v in card_details.items()
            }

            subject = f'New Card Assignment: {card_details["title"]}'
            body = f"""<html>
<body>
<p>Hello {uid},</p>

<p>You have been assigned to the card "<strong>{card_details['title']}</strong>" 
in the stack "<strong>{card_details['stack_title']}</strong>" 
on the board "<strong>{card_details['board_title']}</strong>".</p>

<p><strong>Description:</strong><br>
{card_details['description']}</p>

<p>You can view the card <a href="{NEXTCLOUD_URL}/index.php/apps/deck/#/board/{card_details['board_id']}/card/{card_id}">here</a>.</p>

<p>Best regards,<br>
Your Team</p>
</body>
</html>"""

            try:
                send_email(to_address, subject, body)
                cursor.execute(
                    f"UPDATE {NOTIFICATION_TABLE} SET notified = 1 WHERE id = %s",
                    (notification['id'],)
                )
                logging.info(f'Notification sent to {to_address} for card "{card_details["title"]}"')
            except Exception as e:
                logging.error(f'Error processing notification {notification["id"]}: {e}')

if __name__ == '__main__':
    try:
        process_notifications()
    except Exception as e:
        logging.error(f'Fatal error in main process: {e}')
        raise