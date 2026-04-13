import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
from datetime import datetime

# Moving env loading inside the function to ensure it picks up latest changes
def get_sendgrid_config():
    env_path = r"c:\Users\Kavya Mohan\OneDrive\Desktop\OUR PROJECT\backend\.env"
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL", "noreply@jobtrailsimulator.com")
    return api_key, from_email

async def send_reset_email(to_email: str, reset_link: str):
    """
    Sends a password reset email using SendGrid.
    """
    SENDGRID_API_KEY, FROM_EMAIL = get_sendgrid_config()
    log_path = r"c:\Users\Kavya Mohan\OneDrive\Desktop\OUR PROJECT\backend\email_debug.log"
    
    # Log for debugging
    with open(log_path, "a") as f:
        key_status = "SET" if SENDGRID_API_KEY else "MISSING"
        key_preview = f"{SENDGRID_API_KEY[:10]}..." if SENDGRID_API_KEY else "N/A"
        f.write(f"[{datetime.now()}] Attempting email to {to_email}. Key: {key_status} ({key_preview}), From: {FROM_EMAIL}\n")
    
    if not SENDGRID_API_KEY or "YOUR_SENDGRID" in SENDGRID_API_KEY:
        print(f"ERROR: SENDGRID_API_KEY is not configured correctly. Value: {SENDGRID_API_KEY}")
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now()}] FAILED: API Key not configured correctly.\n")
        return False

    print(f"Sending email using Key: {SENDGRID_API_KEY[:10]}... and From: {FROM_EMAIL}")

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=to_email,
        subject='Reset Your JOB TRAIL SIMULATOR Password',
        html_content=f'''
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px;">
                <h2 style="color: #2563eb;">JOB TRAIL SIMULATOR Password Reset</h2>
                <p>Hello,</p>
                <p>We received a request to reset your password for your JOB TRAIL SIMULATOR account. Click the button below to proceed:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">Reset Password</a>
                </div>
                <p>If you did not request this, you can safely ignore this email.</p>
                <p>Best regards,<br>The JOB TRAIL SIMULATOR Team</p>
                <hr style="border: none; border-top: 1px solid #eee; margin-top: 20px;">
                <p style="font-size: 12px; color: #666;">If the button doesn't work, copy and paste this link into your browser:<br>{reset_link}</p>
            </div>
        '''
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"Email sent successfully. Status code: {response.status_code}")
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now()}] SUCCESS: Status code {response.status_code}\n")
        return True
    except Exception as e:
        import traceback
        error_msg = f"Error sending email via SendGrid: {str(e)}"
        print(error_msg)
        with open(log_path, "a") as f:
            f.write(f"[{datetime.now()}] FAILED: {error_msg}\n")
            f.write(f"{traceback.format_exc()}\n")
        return False
