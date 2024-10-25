# Nextcloud Deck Assignment Notifications

A Python script that sends email notifications to users when they are assigned a new card in Nextcloud Deck.

## Prerequisites

- Python 3.x
- MySQL Server
- An SMTP server (e.g., Mailtrap for testing)

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/yourusername/nextcloud-deck-assignment-notifications.git
   cd nextcloud-deck-assignment-notifications

2. **Setup a Virtual Environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate

3. **Install the Required Packages**

   ```bash
    pip install -r requirements.txt

4. **Create a .env File**
Copy the .env.example file to .env and fill in the required settings.

    ```bash
    cp .env.example .env
    ```

5. **set up a cron job (i used cpanel)**
    - Go to cron jobs in cpanel
    - Add a new cron job
    - Set the command to `python /path/to/main.py` (could also be `python3` depending on your system)
    - Set the frequency to every 5 minutes

    alternatively, you could use crontab on your server

    ```bash
    crontab -e
    ```

    then add the following line to the file

    ```bash
    */5 * * * * /path/to/python /path/to/main.py
    ```

6. **Run the setup script**

    ```bash
    python setup.py

7. **Run the script**

    ```bash
    python main.py
    ```