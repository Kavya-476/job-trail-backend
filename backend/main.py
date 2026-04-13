from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
import models, schemas, auth_utils, database
from services.gemini_service import evaluate_submission
from services.email_service import send_reset_email
from datetime import timedelta, datetime
import os
from google.oauth2 import id_token
from google.auth.transport import requests

app = FastAPI(title="JOB TRAIL SIMULATOR API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional auth for job listings
async def get_optional_user(db: Session = Depends(database.get_db), token: Optional[str] = Depends(auth_utils.oauth2_scheme)):
    if not token:
        return None
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(token, auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        user = db.query(models.User).filter(models.User.email == email).first()
        return user
    except Exception:
        return None

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

@app.get("/stats/total-users")
def get_total_users(db: Session = Depends(database.get_db)):
    count = db.query(models.User).count()
    return {"total_users": count}


@app.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    with open("backend_auth.log", "a") as f:
        f.write(f"Signup attempt: {user.email}\n")
    
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        with open("backend_auth.log", "a") as f:
            f.write(f"Signup failed: {user.email} already exists\n")
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = auth_utils.get_password_hash(user.password)
    new_user = models.User(
        email=user.email, 
        name=user.name, 
        hashed_password=hashed_password,
        education=user.education
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create welcome notification
    welcome_notif = models.Notification(
        user_id=new_user.id,
        title="Welcome to Job Trail Simulator!",
        message="We're excited to have you here. Start exploring our job simulations and build your future career today!",
        type="success"
    )
    db.add(welcome_notif)
    db.commit()
    
    with open("backend_auth.log", "a") as f:
        f.write(f"Signup successful: {user.email}\n")
    return new_user

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    with open("backend_auth.log", "a") as f:
        f.write(f"Login attempt: {form_data.username}\n")
        
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    if not user:
        with open("backend_auth.log", "a") as f:
            f.write(f"Login failed: User {form_data.username} NOT found\n")
    else:
        with open("backend_auth.log", "a") as f:
            f.write(f"Login progress: User {form_data.username} found, verifying password...\n")
        
    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        with open("backend_auth.log", "a") as f:
            f.write(f"Login failed: Invalid credentials for {form_data.username}\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with open("backend_auth.log", "a") as f:
        f.write(f"Login successful: {form_data.username}\n")
    
    # Check for remember_me in a real app, but here we can just use a default or handle it if passed via form
    # FastAPI OAuth2PasswordRequestForm doesn't have remember_me, usually it's a separate field
    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = auth_utils.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/forgot-password")
async def forgot_password(request: schemas.ForgotPasswordRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()
    if not user:
        # For security, we still return success even if user not found to prevent email enumeration
        return {"message": "If this email is registered, you will receive reset instructions."}
    
    # Generate secure random token
    import secrets
    token = secrets.token_urlsafe(32)
    
    # Save token and expiry (1 hour)
    user.reset_token = token
    user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    reset_link = f"http://localhost:5173/reset-password?token={token}&email={user.email}"
    
    email_sent = await send_reset_email(user.email, reset_link)
    
    if email_sent:
        return {"message": "Password reset instructions sent to your email"}
    else:
        # Check why it failed
        from services.email_service import get_sendgrid_config
        key, _ = get_sendgrid_config()
        if not key or "YOUR_SENDGRID" in key:
            detail = "SendGrid API Key is missing or not configured in the .env file."
        else:
            detail = "SendGrid rejected the request (403 Forbidden). Please ensure your 'FROM_EMAIL' is a Verified Sender in your SendGrid dashboard and your API Key has 'Mail Send' permissions."
            
        print(f"CRITICAL: Failed to send reset email to {user.email}. detail: {detail}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

@app.post("/reset-password")
async def reset_password(request: schemas.ResetPasswordRequest, db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(
        models.User.email == request.email,
        models.User.reset_token == request.token
    ).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token or email")
    
    if user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Token has expired")
    
    # Update password and clear token
    user.hashed_password = auth_utils.get_password_hash(request.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()
    
    return {"message": "Password reset successfully"}

@app.post("/auth/google")
async def google_auth(request: schemas.GoogleAuthRequest, db: Session = Depends(database.get_db)):
    try:
        # Verify the ID token
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        # In a real app, you'd use the actual client_id from .env
        # If it's a placeholder, verification might fail if not configured
        idinfo = id_token.verify_oauth2_token(request.token, requests.Request(), client_id)

        email = idinfo['email']
        name = idinfo.get('name', 'Google User')
        
        # Check if user exists
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            # Create a new user if doesn't exist
            user = models.User(email=email, name=name, hashed_password="oauth_google_user")
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Create welcome notification
            welcome_notif = models.Notification(
                user_id=user.id,
                title="Welcome to Job Trail Simulator!",
                message="We're excited to have you here. Start exploring our job simulations and build your future career today!",
                type="success"
            )
            db.add(welcome_notif)
            db.commit()
        
        access_token = auth_utils.create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")
    except Exception as e:
        print(f"Google Auth Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/linkedin")
async def linkedin_auth(db: Session = Depends(database.get_db)):
    # Simulated LinkedIn Auth
    email = "linkedin.user@example.com"
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(email=email, name="LinkedIn User", hashed_password="oauth_simulated")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    access_token = auth_utils.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=schemas.UserMeResponse)
def get_user_me(current_user: models.User = Depends(auth_utils.get_current_user), db: Session = Depends(database.get_db)):
    try:
        # Calculate stats based on submissions
        submissions = db.query(models.Submission).filter(models.Submission.user_id == current_user.id).all()
        unique_task_ids = set([s.task_id for s in submissions])
        simulations_started = len(unique_task_ids)
        
        total_minutes = 0
        for task_id in unique_task_ids:
            task = db.query(models.Task).filter(models.Task.id == task_id).first()
            if task and task.duration:
                total_minutes += task.duration
            elif task:
                total_minutes += 30 # Default to 30 mins if null
                
        hours_learned = round(total_minutes / 60, 1)
        
        stats = {
            "simulationsStarted": simulations_started,
            "hoursLearned": hours_learned,
            "badgesEarned": simulations_started // 3
        }
    except Exception as e:
        print(f"Error calculating user stats: {e}")
        stats = {
            "simulationsStarted": 0,
            "hoursLearned": 0.0,
            "badgesEarned": 0
        }
    
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "education": current_user.education,
        "created_at": current_user.created_at,
        "stats": stats
    }

@app.patch("/users/me", response_model=schemas.UserResponse)
def update_profile(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(auth_utils.get_current_user),
    db: Session = Depends(database.get_db)
):
    if user_update.name is not None:
        current_user.name = user_update.name
    if user_update.email is not None:
        # Check if email is already taken
        if user_update.email != current_user.email:
            existing_user = db.query(models.User).filter(models.User.email == user_update.email).first()
            if existing_user:
                raise HTTPException(status_code=400, detail="Email already taken")
            current_user.email = user_update.email
    if user_update.education is not None:
        current_user.education = user_update.education
    if user_update.created_at is not None:
        current_user.created_at = user_update.created_at
    
    db.commit()
    db.refresh(current_user)
    return current_user

@app.get("/jobs", response_model=List[schemas.JobBase])
def get_jobs(db: Session = Depends(database.get_db), current_user: Optional[models.User] = Depends(get_optional_user)):
    print("DEBUG: get_jobs endpoint called")
    from sqlalchemy import func
    jobs = db.query(models.Job).all()
    
    result = []
    for job in jobs:
        print(f"DEBUG: Processing job {job.id}")
        # Count unique user_ids who submitted to any task in this job
        count = db.query(func.count(func.distinct(models.Submission.user_id)))\
            .join(models.Task, models.Submission.task_id == models.Task.id)\
            .filter(models.Task.job_id == job.id).scalar()
        
        # Check if wishlisted by current user
        is_wishlisted = False
        if current_user:
            wish = db.query(models.Wishlist).filter(
                models.Wishlist.user_id == current_user.id,
                models.Wishlist.job_id == job.id
            ).first()
            is_wishlisted = wish is not None

        # Manually construct the response to ensure all fields are included
        job_dict = {
            "id": job.id,
            "title": job.title,
            "description": job.description,
            "category": job.category,
            "image_url": job.image_url,
            "participant_count": count or 0,
            "is_wishlisted": is_wishlisted,
            "is_upcoming": True if (job.is_upcoming or job.id in ['job_uiux', 'job_data', 'job_test', 'job_db']) else False,
            "skills": job.skills.split(",") if job.skills else [],
            "tasks": job.tasks
        }
        result.append(job_dict)
        
    return result

@app.get("/jobs/{job_id}", response_model=schemas.JobBase)
def get_job(job_id: str, db: Session = Depends(database.get_db), current_user: Optional[models.User] = Depends(get_optional_user)):
    from sqlalchemy import func
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    count = db.query(func.count(func.distinct(models.Submission.user_id)))\
        .join(models.Task, models.Submission.task_id == models.Task.id)\
        .filter(models.Task.job_id == job.id).scalar()
        
    
    # Check if wishlisted
    is_wishlisted = False
    if current_user:
        wish = db.query(models.Wishlist).filter(
            models.Wishlist.user_id == current_user.id,
            models.Wishlist.job_id == job.id
        ).first()
        is_wishlisted = wish is not None

    return {
        "id": job.id,
        "title": job.title,
        "description": job.description,
        "category": job.category,
        "image_url": job.image_url,
        "participant_count": count or 0,
        "is_wishlisted": is_wishlisted,
        "is_upcoming": True if job.is_upcoming else False, # Explicit casting
        "skills": job.skills.split(",") if job.skills else [],
        "tasks": job.tasks
    }

# Wishlist Endpoints
@app.post("/wishlist/toggle/{job_id}")
def toggle_wishlist(job_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    wish = db.query(models.Wishlist).filter(
        models.Wishlist.user_id == current_user.id,
        models.Wishlist.job_id == job_id
    ).first()
    
    if wish:
        db.delete(wish)
        db.commit()
        return {"status": "removed", "is_wishlisted": False}
    else:
        new_wish = models.Wishlist(user_id=current_user.id, job_id=job_id)
        db.add(new_wish)
        db.commit()
        return {"status": "added", "is_wishlisted": True}

@app.get("/wishlist", response_model=List[schemas.JobBase])
def get_wishlist(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    wishlisted_jobs = db.query(models.Job).join(models.Wishlist).filter(models.Wishlist.user_id == current_user.id).all()
    
    from sqlalchemy import func
    result = []
    for job in wishlisted_jobs:
        count = db.query(func.count(func.distinct(models.Submission.user_id)))\
            .join(models.Task, models.Submission.task_id == models.Task.id)\
            .filter(models.Task.job_id == job.id).scalar()
            
        result.append({
            "id": job.id,
            "title": job.title,
            "description": job.description,
            "category": job.category,
            "image_url": job.image_url,
            "participant_count": count or 0,
            "is_wishlisted": True,
            "tasks": job.tasks
        })
    return result

@app.get("/jobs/{job_id}/tasks", response_model=List[schemas.TaskBase])
def get_job_tasks(job_id: str, level: str = None, db: Session = Depends(database.get_db)):
    query = db.query(models.Task).filter(models.Task.job_id == job_id)
    if level:
        query = query.filter(models.Task.level == level)
    return query.all()

@app.post("/submit", response_model=schemas.SubmissionResponse)
async def submit_task(
    submission: schemas.SubmissionCreate, 
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth_utils.get_current_user)
):
    try:
        task = db.query(models.Task).filter(models.Task.id == submission.task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # AI Evaluation using Gemini
        print(f"Evaluating submission for task: {task.title}")
        evaluation_result = await evaluate_submission(task.title, task.description, submission.content)
        print(f"Evaluation result: {evaluation_result}")
        
        # Serialize the structured feedback to store in the DB
        import json
        feedback_str = json.dumps(evaluation_result)
        
        new_submission = models.Submission(
            user_id=current_user.id,
            task_id=submission.task_id,
            content=submission.content,
            score=evaluation_result.get("score", 0),
            feedback=feedback_str
        )
        db.add(new_submission)
        db.commit()
        db.refresh(new_submission)
        return new_submission
    except Exception as e:
        import traceback
        with open("backend_debug_submit.log", "a") as f:
            f.write(f"Error in submit_task: {str(e)}\n")
            f.write(traceback.format_exc())
            f.write("\n" + "-"*20 + "\n")
        print(f"ERROR in submit_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/submissions/me", response_model=List[schemas.SubmissionHistory])
def get_user_submissions(current_user: models.User = Depends(auth_utils.get_current_user), db: Session = Depends(database.get_db)):
    submissions = db.query(models.Submission).filter(models.Submission.user_id == current_user.id).order_by(models.Submission.created_at.desc()).all()
    
    history = []
    for sub in submissions:
        task = db.query(models.Task).filter(models.Task.id == sub.task_id).first()
        job = db.query(models.Job).filter(models.Job.id == task.job_id).first() if task else None
        
        history.append({
            "id": sub.id,
            "task_id": sub.task_id,
            "task_title": task.title if task else "Unknown Task",
            "job_title": job.title if job else "Unknown Job",
            "date": sub.created_at.strftime("%Y-%m-%d"),
            "status": "Completed", # Simplified
            "score": sub.score
        })
    
    return history

@app.get("/notifications", response_model=List[schemas.NotificationResponse])
def get_notifications(current_user: models.User = Depends(auth_utils.get_current_user), db: Session = Depends(database.get_db)):
    return db.query(models.Notification).filter(models.Notification.user_id == current_user.id).order_by(models.Notification.created_at.desc()).all()

@app.patch("/notifications/{notification_id}/read", response_model=schemas.NotificationResponse)
def mark_notification_read(notification_id: int, current_user: models.User = Depends(auth_utils.get_current_user), db: Session = Depends(database.get_db)):
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id, models.Notification.user_id == current_user.id).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.read = 1
    db.commit()
    db.refresh(notification)
    return notification

@app.get("/health")
def health_check():
    # Health check endpoint
    return {"status": "healthy"}
