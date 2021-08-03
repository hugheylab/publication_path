import smtplib, ssl
from c3po.db import get_db
from c3po.db import pg_query
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(receiver_email, message_text, subject, db):
    # Uncomment below lines to re-add whitelisting emails
    # cur = db.cursor()
    # cur.execute(
    #     'SELECT * FROM accept_email WHERE active = TRUE', 
    # )
    # acceptEmailList = cur.fetchall()
    # cur.close()
    # acceptEmail = []
    # if acceptEmailList != None and len(acceptEmailList) > 0:
    #     for acceptEmailTmp in acceptEmailList:
    #         acceptEmail.append(acceptEmailTmp['email'])
    acceptEmail = [receiver_email]
    if receiver_email in acceptEmail:
        cur = db.cursor()
        smtp_server = "smtp.gmail.com"
        port = 587  # For starttls
        cur.execute(
            'SELECT * FROM email_address WHERE active = TRUE', 
        )
        emailSender = cur.fetchone()
        sender_email = emailSender['email']
        password = emailSender['password']

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = receiver_email

        text_part = MIMEText(message_text, "html")
        message.attach(text_part)

        # Create a secure SSL context
        context = ssl.create_default_context()

        # Try to log in to server and send email
        try:
            server = smtplib.SMTP(smtp_server,port)
            server.ehlo() # Can be omitted
            server.starttls(context=context) # Secure the connection
            server.ehlo() # Can be omitted
            server.login(sender_email, password)

            server.sendmail(sender_email, receiver_email, message.as_string())

        except Exception as e:
            # Print any error messages to stdout
            print(e)
        finally:
            server.quit() 