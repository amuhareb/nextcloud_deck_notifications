import os
from dotenv import load_dotenv
import mysql.connector
import smtplib
from email.mime.text import MIMEText
import logging

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

# Table prefixes and names
DB_PREFIX = os.getenv('DB_PREFIX', '')
USER_TABLE = os.getenv('USER_TABLE', f'{DB_PREFIX}users')
ASSIGNMENT_TABLE = os.getenv('ASSIGNMENT_TABLE', 'assignment_notifications')

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM')

def send_email(to_address, subject, body):
    logging.info(f'Sending email to {to_address}')
    msg = MIMEText(body, 'html')
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

def get_user_emails():
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True)
    query = f"SELECT uid, email FROM {USER_TABLE}"
    cursor.execute(query)
    users = cursor.fetchall()
    cursor.close()
    cnx.close()
    user_emails = {user['uid']: user['email'] for user in users if user['email']}
    return user_emails

def get_card_details(card_id):
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor()
    query = f"""
    SELECT c.title, c.description, b.title AS board_title, s.title AS stack_title
    FROM {DB_PREFIX}deck_cards c
    JOIN {DB_PREFIX}deck_stacks s ON c.stack_id = s.id
    JOIN {DB_PREFIX}deck_boards b ON s.board_id = b.id
    WHERE c.id = %s
    """
    cursor.execute(query, (card_id,))
    result = cursor.fetchone()
    cursor.close()
    cnx.close()
    if result:
        return {
            'title': result[0],
            'description': result[1],
            'board_title': result[2],
            'stack_title': result[3],
        }
    else:
        return None

def check_and_create_table():
    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor()
    query = f"""
    CREATE TABLE IF NOT EXISTS {ASSIGNMENT_TABLE} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        card_id INT NOT NULL,
        participant VARCHAR(255) NOT NULL,
        notified BOOLEAN DEFAULT FALSE
    )
    """
    cursor.execute(query)
    cnx.commit()
    cursor.close()
    cnx.close()

def process_notifications():
    check_and_create_table()
    user_emails = get_user_emails()

    cnx = mysql.connector.connect(**db_config)
    cursor = cnx.cursor(dictionary=True)
    update_cursor = cnx.cursor()
    query = f"SELECT * FROM {ASSIGNMENT_TABLE} WHERE notified = 0"
    cursor.execute(query)
    notifications = cursor.fetchall()

    for notification in notifications:
        card_id = notification['card_id']
        uid = notification['participant']
        to_address = user_emails.get(uid)
        if to_address:
            card_details = get_card_details(card_id)
            if not card_details:
                logging.warning(f'Card details not found for card_id {card_id}')
                continue
            card_title = card_details['title']
            card_description = card_details['description']
            board_title = card_details['board_title']
            stack_title = card_details['stack_title']

            subject = 'You have been assigned a new card'

            body = f"""<html>
<body>
<p>Hello {uid},</p>

<p>You have been assigned to the card "<strong>{card_title}</strong>" in the stack "<strong>{stack_title}</strong>" on the board "<strong>{board_title}</strong>".</p>

<p><strong>Description:</strong><br>
{card_description}</p>

<p>You can view the card <a href="https://nextcloud.yourdomain.com/index.php/apps/deck/#/board/{card_id}">here</a>.</p>

<p>Best regards,<br>
Your Team</p>
</body>
</html>
"""
            try:
                send_email(to_address, subject, body)
                # Update notified status
                update_query = f"UPDATE {ASSIGNMENT_TABLE} SET notified = 1 WHERE id = %s"
                update_cursor.execute(update_query, (notification['id'],))
                cnx.commit()
                logging.info(f'Notification sent to {to_address} for card "{card_title}"')
            except Exception as e:
                logging.error(f'Error sending email to {to_address}: {e}')
        else:
            logging.warning(f'No email found for user {uid}')

    logging.info(f'{len(notifications)} notifications processed')
    cursor.close()
    update_cursor.close()
    cnx.close()

if __name__ == '__main__':
    process_notifications()

