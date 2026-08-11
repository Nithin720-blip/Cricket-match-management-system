import os
import shutil
import hashlib
from datetime import datetime
from fastapi import FastAPI, Depends, Request, Form, File, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from database import engine, get_db
import models

# Make sure directories exist
os.makedirs("uploads/players", exist_ok=True)
os.makedirs("images/logos", exist_ok=True)

app = FastAPI(title="Elite Cricket Management System")

# Session Middleware for session-based auth (like $_SESSION in PHP)
app.add_middleware(SessionMiddleware, secret_key="elite-cricket-management-super-secret-key")

# Static mounting so HTML files can find css, js, and uploaded images directly
app.mount("/assets", StaticFiles(directory="assets"), name="assets")
app.mount("/images", StaticFiles(directory="images"), name="images")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

# Context processor for templates to fetch session messages automatically
def get_session_message(request: Request):
    msg = request.session.pop("message", None)
    return msg

# Auth checks
def is_admin_logged_in(request: Request) -> bool:
    return request.session.get("admin_logged_in") == True

# Helper functions for calculations
def balls_to_overs(balls: int) -> str:
    if not balls:
        return '0.0'
    overs_full = balls // 6
    balls_rem = balls % 6
    return f"{overs_full}.{balls_rem}"

def calculate_economy_rate(runs_conceded: int, balls_bowled: int) -> str:
    if not balls_bowled:
        return '0.00'
    return f"{runs_conceded / (balls_bowled / 6):.2f}"


# --- CUSTOM ROUTES ---

# Home Gateway
@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


# --- ADMIN ROUTING ---

# Admin Login (GET)
@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    if is_admin_logged_in(request):
        return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    error = request.session.pop("error", "")
    reset_message = request.session.pop("reset_message", "")
    return templates.TemplateResponse(request, "admin/admin_login.html", {
        "request": request, 
        "error": error, 
        "reset_message": reset_message,
        "username_login": "",
        "reset_username": ""
    })

# Admin Login & Reset Password (POST)
@app.post("/admin/login")
def admin_login_submit(
    request: Request,
    db: Session = Depends(get_db),
    action: str = Form(None),
    username: str = Form(None),
    password: str = Form(None),
    reset_username: str = Form(None),
    new_password: str = Form(None),
    confirm_password: str = Form(None)
):
    if action == "reset_password_direct":
        if not reset_username or not new_password or not confirm_password:
            request.session["reset_message"] = '<div class="alert alert-error"><i class="fas fa-exclamation-circle"></i> Please fill in all fields.</div>'
        elif new_password != confirm_password:
            request.session["reset_message"] = '<div class="alert alert-error"><i class="fas fa-exclamation-circle"></i> New password and confirm password do not match.</div>'
        else:
            hashed_pw = hashlib.sha256(new_password.encode()).hexdigest()
            admin = db.query(models.Admin).filter(models.Admin.username == reset_username).first()
            if admin:
                admin.password = hashed_pw
                db.commit()
                request.session["reset_message"] = '<div class="alert alert-success"><i class="fas fa-check-circle"></i> Your password has been reset. You can now log in.</div>'
            else:
                request.session["reset_message"] = '<div class="alert alert-error"><i class="fas fa-exclamation-circle"></i> Failed to reset password. Username not found.</div>'
        
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    else:
        if not username or not password:
            request.session["error"] = "Please fill in all fields."
            return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
        
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        admin = db.query(models.Admin).filter(models.Admin.username == username).first()
        
        if admin and admin.password == hashed_pw:
            request.session["admin_logged_in"] = True
            request.session["admin_username"] = admin.username
            request.session["admin_id"] = admin.admin_id
            return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        else:
            request.session["error"] = "Invalid username or password."
            return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

# Admin Logout
@app.get("/admin/logout")
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# Admin Dashboard
@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "admin/admin_dashboard.html", {"request": request})


# Admin Manage Players (GET)
@app.get("/admin/manage_players", response_class=HTMLResponse)
def manage_players(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    # Handle deletion
    if delete is not None:
        player = db.query(models.Player).filter(models.Player.player_id == delete).first()
        if player:
            # unlink photo file
            if player.player_photo:
                photo_path = os.path.join("uploads/players", player.player_photo)
                if os.path.exists(photo_path) and os.path.isfile(photo_path):
                    try:
                        os.remove(photo_path)
                    except Exception:
                        pass
            db.delete(player)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Player deleted successfully!"}
        return RedirectResponse(url="/admin/manage_players", status_code=status.HTTP_303_SEE_OTHER)

    # Fetch players and teams
    players = db.query(models.Player).join(models.Team).order_by(models.Player.player_name.asc()).all()
    teams = db.query(models.Team).order_by(models.Team.team_name.asc()).all()
    
    edit_player_data = None
    if edit is not None:
        edit_player_data = db.query(models.Player).filter(models.Player.player_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/manage_players.html", {
        "request": request,
        "players": players,
        "teams": teams,
        "edit_player_data": edit_player_data,
        "message": message
    })

# Admin Manage Players (POST)
@app.post("/admin/manage_players")
def manage_players_submit(
    request: Request,
    submit_form: str = Form(...),
    player_id: str = Form(None),
    player_name: str = Form(...),
    age: int = Form(...),
    role: str = Form(...),
    team_id: int = Form(...),
    player_photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    player_name = player_name.strip()
    is_update = player_id is not None and player_id != ''
    pid = int(player_id) if is_update else 0

    if not player_name or age <= 0 or not role or team_id <= 0:
        request.session["message"] = {"type": "error", "text": "Please fill in all player details correctly."}
        return RedirectResponse(url="/admin/manage_players", status_code=status.HTTP_303_SEE_OTHER)

    # Check duplicate
    dup_query = db.query(models.Player).filter(models.Player.player_name == player_name)
    if is_update:
        dup_query = dup_query.filter(models.Player.player_id != pid)
    
    if dup_query.first():
        request.session["message"] = {"type": "error", "text": "A player with this name already exists."}
        return RedirectResponse(url="/admin/manage_players", status_code=status.HTTP_303_SEE_OTHER)

    # Save photo
    photo_name = ""
    if player_photo and player_photo.filename:
        photo_name = player_photo.filename
        target_path = os.path.join("uploads/players", photo_name)
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(player_photo.file, buffer)

    if is_update:
        player = db.query(models.Player).filter(models.Player.player_id == pid).first()
        if player:
            player.player_name = player_name
            player.age = age
            player.role = role
            player.team_id = team_id
            if photo_name:
                player.player_photo = photo_name
            db.commit()
            request.session["message"] = {"type": "success", "text": "Player updated successfully!"}
    else:
        new_player = models.Player(
            player_name=player_name,
            age=age,
            role=role,
            team_id=team_id,
            player_photo=photo_name
        )
        db.add(new_player)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Player added successfully!"}

    return RedirectResponse(url="/admin/manage_players", status_code=status.HTTP_303_SEE_OTHER)


# Admin Manage Teams (GET)
@app.get("/admin/manage_teams", response_class=HTMLResponse)
def manage_teams(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    # Handle deletion
    if delete is not None:
        team = db.query(models.Team).filter(models.Team.team_id == delete).first()
        if team:
            # unlink logo file if local
            if team.logo:
                logo_path = os.path.join("uploads", team.logo) if not team.logo.startswith("images/logos/") else team.logo
                if os.path.exists(logo_path) and os.path.isfile(logo_path):
                    try:
                        os.remove(logo_path)
                    except Exception:
                        pass
            db.delete(team)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Team deleted successfully!"}
        return RedirectResponse(url="/admin/manage_teams", status_code=status.HTTP_303_SEE_OTHER)

    teams = db.query(models.Team, models.Venue.venue_name).outerjoin(
        models.Venue, models.Team.home_ground == models.Venue.venue_id
    ).order_by(models.Team.team_id.desc()).all()
    
    venues = db.query(models.Venue).order_by(models.Venue.venue_name.asc()).all()
    
    edit_team_data = None
    if edit is not None:
        edit_team_data = db.query(models.Team).filter(models.Team.team_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/manage_teams.html", {
        "request": request,
        "teams": teams,
        "venues": venues,
        "edit_team_data": edit_team_data,
        "message": message
    })

# Admin Manage Teams (POST)
@app.post("/admin/manage_teams")
def manage_teams_submit(
    request: Request,
    submit_form: str = Form(...),
    team_id: str = Form(None),
    team_name: str = Form(...),
    captain_name: str = Form(""),
    coach_name: str = Form(""),
    home_ground: int = Form(...),
    wins: int = Form(0),
    losses: int = Form(0),
    draws: int = Form(0),
    points: int = Form(0),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    team_name = team_name.strip()
    is_update = team_id is not None and team_id != ''
    tid = int(team_id) if is_update else 0

    if not team_name or not coach_name or not captain_name or home_ground <= 0:
        request.session["message"] = {"type": "error", "text": "Please fill in all team details correctly."}
        return RedirectResponse(url="/admin/manage_teams", status_code=status.HTTP_303_SEE_OTHER)

    # Check duplicate
    dup_query = db.query(models.Team).filter(models.Team.team_name == team_name)
    if is_update:
        dup_query = dup_query.filter(models.Team.team_id != tid)
    if dup_query.first():
        request.session["message"] = {"type": "error", "text": "A team with this name already exists."}
        return RedirectResponse(url="/admin/manage_teams", status_code=status.HTTP_303_SEE_OTHER)

    # Save logo file
    logo_name = ""
    if logo and logo.filename:
        logo_name = logo.filename
        target_path = os.path.join("uploads", logo_name)
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)

    if is_update:
        team = db.query(models.Team).filter(models.Team.team_id == tid).first()
        if team:
            team.team_name = team_name
            team.captain_name = captain_name
            team.coach_name = coach_name
            team.home_ground = home_ground
            team.wins = wins
            team.losses = losses
            team.draws = draws
            team.points = points
            if logo_name:
                team.logo = logo_name
            db.commit()
            request.session["message"] = {"type": "success", "text": "Team updated successfully!"}
    else:
        new_team = models.Team(
            team_name=team_name,
            captain_name=captain_name,
            coach_name=coach_name,
            home_ground=home_ground,
            logo=logo_name,
            wins=wins,
            losses=losses,
            draws=draws,
            points=points
        )
        db.add(new_team)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Team added successfully!"}

    return RedirectResponse(url="/admin/manage_teams", status_code=status.HTTP_303_SEE_OTHER)

# Admin Upload Team Logo (POST & GET)
@app.get("/admin/upload_logo", response_class=HTMLResponse)
def upload_logo_page(request: Request):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "admin/upload_logo.html", {"request": request})

@app.post("/admin/upload_logo")
def upload_logo_submit(
    request: Request,
    team_id: str = Form(...),
    logo: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    
    if logo and logo.filename:
        ext = os.path.splitext(logo.filename)[1].lower()
        filename = f"{team_id.lower()}{ext}"
        target_path = os.path.join("images/logos", filename)
        
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
            
        db_path = f"images/logos/{filename}"
        team = db.query(models.Team).filter(models.Team.team_id == int(team_id)).first()
        if team:
            team.logo = db_path
            db.commit()
            return HTMLResponse(content="Logo uploaded and updated successfully!")
        
    return HTMLResponse(content="File upload error.")


# Admin Manage Matches (GET)
@app.get("/admin/manage_matches", response_class=HTMLResponse)
def manage_matches(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    if delete is not None:
        match = db.query(models.Match).filter(models.Match.match_id == delete).first()
        if match:
            db.delete(match)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Match deleted successfully!"}
        return RedirectResponse(url="/admin/manage_matches", status_code=status.HTTP_303_SEE_OTHER)

    matches = db.query(models.Match).order_by(models.Match.match_date.desc()).all()
    teams = db.query(models.Team).order_by(models.Team.team_name.asc()).all()
    venues = db.query(models.Venue).order_by(models.Venue.venue_name.asc()).all()

    edit_match_data = None
    if edit is not None:
        edit_match_data = db.query(models.Match).filter(models.Match.match_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/manage_matches.html", {
        "request": request,
        "matches": matches,
        "teams": teams,
        "venues": venues,
        "edit_match_data": edit_match_data,
        "message": message
    })

# Admin Manage Matches (POST)
@app.post("/admin/manage_matches")
def manage_matches_submit(
    request: Request,
    submit_form: str = Form(...),
    match_id: str = Form(None),
    match_date: str = Form(...),
    team1_id: int = Form(...),
    team2_id: int = Form(...),
    venue_id: int = Form(...),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    is_update = match_id is not None and match_id != ''
    mid = int(match_id) if is_update else 0

    if not match_date or team1_id <= 0 or team2_id <= 0 or venue_id <= 0:
        request.session["message"] = {"type": "error", "text": "Please fill in all details correctly."}
        return RedirectResponse(url="/admin/manage_matches", status_code=status.HTTP_303_SEE_OTHER)

    if team1_id == team2_id:
        request.session["message"] = {"type": "error", "text": "A team cannot play against itself."}
        return RedirectResponse(url="/admin/manage_matches", status_code=status.HTTP_303_SEE_OTHER)

    date_obj = datetime.strptime(match_date, "%Y-%m-%d").date()

    if is_update:
        match = db.query(models.Match).filter(models.Match.match_id == mid).first()
        if match:
            match.match_date = date_obj
            match.team1_id = team1_id
            match.team2_id = team2_id
            match.venue_id = venue_id
            db.commit()
            request.session["message"] = {"type": "success", "text": "Match updated successfully!"}
    else:
        new_match = models.Match(
            match_date=date_obj,
            team1_id=team1_id,
            team2_id=team2_id,
            venue_id=venue_id
        )
        db.add(new_match)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Match scheduled successfully!"}

    return RedirectResponse(url="/admin/manage_matches", status_code=status.HTTP_303_SEE_OTHER)


# Admin Manage Venues (GET)
@app.get("/admin/manage_venues", response_class=HTMLResponse)
def manage_venues(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    if delete is not None:
        venue = db.query(models.Venue).filter(models.Venue.venue_id == delete).first()
        if venue:
            db.delete(venue)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Venue deleted successfully!"}
        return RedirectResponse(url="/admin/manage_venues", status_code=status.HTTP_303_SEE_OTHER)

    venues = db.query(models.Venue).order_by(models.Venue.venue_name.asc()).all()
    edit_venue_data = None
    if edit is not None:
        edit_venue_data = db.query(models.Venue).filter(models.Venue.venue_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/manage_venues.html", {
        "request": request,
        "venues": venues,
        "edit_venue_data": edit_venue_data,
        "message": message
    })

# Admin Manage Venues (POST)
@app.post("/admin/manage_venues")
def manage_venues_submit(
    request: Request,
    submit_form: str = Form(...),
    venue_id: str = Form(None),
    venue_name: str = Form(...),
    city: str = Form(""),
    capacity: int = Form(0),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    venue_name = venue_name.strip()
    is_update = venue_id is not None and venue_id != ''
    vid = int(venue_id) if is_update else 0

    if not venue_name:
        request.session["message"] = {"type": "error", "text": "Venue Name is required."}
        return RedirectResponse(url="/admin/manage_venues", status_code=status.HTTP_303_SEE_OTHER)

    # Check duplicate
    dup_query = db.query(models.Venue).filter(models.Venue.venue_name == venue_name)
    if is_update:
        dup_query = dup_query.filter(models.Venue.venue_id != vid)
    if dup_query.first():
        request.session["message"] = {"type": "error", "text": "A venue with this name already exists."}
        return RedirectResponse(url="/admin/manage_venues", status_code=status.HTTP_303_SEE_OTHER)

    if is_update:
        venue = db.query(models.Venue).filter(models.Venue.venue_id == vid).first()
        if venue:
            venue.venue_name = venue_name
            venue.city = city
            venue.capacity = capacity
            db.commit()
            request.session["message"] = {"type": "success", "text": "Venue updated successfully!"}
    else:
        new_venue = models.Venue(
            venue_name=venue_name,
            city=city,
            capacity=capacity
        )
        db.add(new_venue)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Venue added successfully!"}

    return RedirectResponse(url="/admin/manage_venues", status_code=status.HTTP_303_SEE_OTHER)


# Admin Manage Scorecards (GET)
@app.get("/admin/manage_scorecards", response_class=HTMLResponse)
def manage_scorecards(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    if delete is not None:
        scorecard = db.query(models.Scorecard).filter(models.Scorecard.scorecard_id == delete).first()
        if scorecard:
            db.delete(scorecard)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Scorecard entry deleted successfully!"}
        return RedirectResponse(url="/admin/manage_scorecards", status_code=status.HTTP_303_SEE_OTHER)

    # Fetch scorecards with relations
    scorecards = db.query(models.Scorecard).join(models.Match).join(models.Player).order_by(models.Match.match_date.desc()).all()
    
    # Fetch active scheduled matches (where we want to record scorecard)
    matches = db.query(models.Match).order_by(models.Match.match_date.desc()).all()
    
    edit_scorecard_data = None
    if edit is not None:
        edit_scorecard_data = db.query(models.Scorecard).filter(models.Scorecard.scorecard_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/manage_scorecards.html", {
        "request": request,
        "scorecards": scorecards,
        "matches": matches,
        "edit_scorecard_data": edit_scorecard_data,
        "message": message
    })

# Admin Manage Scorecards (POST)
@app.post("/admin/manage_scorecards")
def manage_scorecards_submit(
    request: Request,
    submit_form: str = Form(...),
    scorecard_id: str = Form(None),
    match_id: int = Form(...),
    player_id: int = Form(...),
    runs: int = Form(0),
    wickets: int = Form(0),
    runs_conceded: int = Form(0),
    balls_faced_batting: int = Form(0),
    balls_bowled_bowling: int = Form(0),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    is_update = scorecard_id is not None and scorecard_id != ''
    sid = int(scorecard_id) if is_update else 0

    if match_id <= 0 or player_id <= 0:
        request.session["message"] = {"type": "error", "text": "Match and Player selections are required."}
        return RedirectResponse(url="/admin/manage_scorecards", status_code=status.HTTP_303_SEE_OTHER)

    # Check duplicate
    dup_query = db.query(models.Scorecard).filter(
        and_(
            models.Scorecard.match_id == match_id,
            models.Scorecard.player_id == player_id
        )
    )
    if is_update:
        dup_query = dup_query.filter(models.Scorecard.scorecard_id != sid)
    if dup_query.first():
        request.session["message"] = {"type": "error", "text": "A scorecard entry for this player in this match already exists."}
        return RedirectResponse(url="/admin/manage_scorecards", status_code=status.HTTP_303_SEE_OTHER)

    if is_update:
        scorecard = db.query(models.Scorecard).filter(models.Scorecard.scorecard_id == sid).first()
        if scorecard:
            scorecard.match_id = match_id
            scorecard.player_id = player_id
            scorecard.runs = runs
            scorecard.wickets = wickets
            scorecard.runs_conceded = runs_conceded
            scorecard.balls_faced_batting = balls_faced_batting
            scorecard.balls_bowled_bowling = balls_bowled_bowling
            db.commit()
            request.session["message"] = {"type": "success", "text": "Scorecard entry updated successfully!"}
    else:
        new_scorecard = models.Scorecard(
            match_id=match_id,
            player_id=player_id,
            runs=runs,
            wickets=wickets,
            runs_conceded=runs_conceded,
            balls_faced_batting=balls_faced_batting,
            balls_bowled_bowling=balls_bowled_bowling
        )
        db.add(new_scorecard)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Scorecard entry added successfully!"}

    return RedirectResponse(url="/admin/manage_scorecards", status_code=status.HTTP_303_SEE_OTHER)

# AJAX - Retrieve players for a specific match's teams
@app.get("/admin/get_players_by_match")
def get_players_by_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.match_id == match_id).first()
    if not match:
        return JSONResponse(content=[])
    
    players = db.query(models.Player).filter(
        models.Player.team_id.in_([match.team1_id, match.team2_id])
    ).order_by(models.Player.player_name.asc()).all()
    
    out = []
    for p in players:
        out.append({
            "player_id": p.player_id,
            "player_name": p.player_name,
            "role": p.role
        })
    return JSONResponse(content=out)


# Admin Match Summaries (GET)
@app.get("/admin/match_summaries", response_class=HTMLResponse)
def match_summaries(
    request: Request,
    edit: int = None,
    delete: int = None,
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    if delete is not None:
        summary = db.query(models.MatchSummary).filter(models.MatchSummary.summary_id == delete).first()
        if summary:
            db.delete(summary)
            db.commit()
            request.session["message"] = {"type": "success", "text": "Match summary deleted successfully!"}
        return RedirectResponse(url="/admin/match_summaries", status_code=status.HTTP_303_SEE_OTHER)

    summaries = db.query(models.MatchSummary).join(models.Match).order_by(models.Match.match_date.desc()).all()
    matches = db.query(models.Match).order_by(models.Match.match_date.desc()).all()

    edit_summary_data = None
    if edit is not None:
        edit_summary_data = db.query(models.MatchSummary).filter(models.MatchSummary.summary_id == edit).first()

    message = get_session_message(request)
    return templates.TemplateResponse(request, "admin/match_summaries.html", {
        "request": request,
        "summaries": summaries,
        "matches": matches,
        "edit_summary_data": edit_summary_data,
        "message": message
    })

# Admin Match Summaries (POST)
@app.post("/admin/match_summaries")
def match_summaries_submit(
    request: Request,
    submit_form: str = Form(...),
    summary_id: str = Form(None),
    match_id: int = Form(...),
    team1_score: int = Form(0),
    team1_wickets: int = Form(0),
    team2_score: int = Form(0),
    team2_wickets: int = Form(0),
    result: str = Form(""),
    db: Session = Depends(get_db)
):
    if not is_admin_logged_in(request):
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)

    is_update = summary_id is not None and summary_id != ''
    sid = int(summary_id) if is_update else 0

    if match_id <= 0:
        request.session["message"] = {"type": "error", "text": "Match selection is required."}
        return RedirectResponse(url="/admin/match_summaries", status_code=status.HTTP_303_SEE_OTHER)

    # Check duplicate summary for the same match
    dup_query = db.query(models.MatchSummary).filter(models.MatchSummary.match_id == match_id)
    if is_update:
        dup_query = dup_query.filter(models.MatchSummary.summary_id != sid)
    if dup_query.first():
        request.session["message"] = {"type": "error", "text": "A summary for this match already exists."}
        return RedirectResponse(url="/admin/match_summaries", status_code=status.HTTP_303_SEE_OTHER)

    if is_update:
        summary = db.query(models.MatchSummary).filter(models.MatchSummary.summary_id == sid).first()
        if summary:
            summary.match_id = match_id
            summary.team1_score = team1_score
            summary.team1_wickets = team1_wickets
            summary.team2_score = team2_score
            summary.team2_wickets = team2_wickets
            summary.result = result
            db.commit()
            request.session["message"] = {"type": "success", "text": "Match summary updated successfully!"}
    else:
        new_summary = models.MatchSummary(
            match_id=match_id,
            team1_score=team1_score,
            team1_wickets=team1_wickets,
            team2_score=team2_score,
            team2_wickets=team2_wickets,
            result=result
        )
        db.add(new_summary)
        db.commit()
        request.session["message"] = {"type": "success", "text": "Match summary added successfully!"}

    return RedirectResponse(url="/admin/match_summaries", status_code=status.HTTP_303_SEE_OTHER)


# --- USER ROUTING ---

# User Dashboard
@app.get("/user/dashboard", response_class=HTMLResponse)
def user_dashboard(request: Request):
    return templates.TemplateResponse(request, "user/user_dashboard.html", {"request": request})

# View Match Schedule
@app.get("/user/view_matches", response_class=HTMLResponse)
def view_matches(request: Request, db: Session = Depends(get_db)):
    finished_matches = db.query(models.Match).join(models.MatchSummary).order_by(models.Match.match_date.desc()).all()
    upcoming_matches = db.query(models.Match).outerjoin(models.MatchSummary).filter(models.MatchSummary.match_id == None).order_by(models.Match.match_date.asc()).all()
    return templates.TemplateResponse(request, "user/view_matches.html", {
        "request": request, 
        "finished_matches": finished_matches,
        "upcoming_matches": upcoming_matches
    })

# View Teams List
@app.get("/user/view_teams", response_class=HTMLResponse)
def view_teams(request: Request, db: Session = Depends(get_db)):
    teams = db.query(models.Team, models.Venue.venue_name).outerjoin(
        models.Venue, models.Team.home_ground == models.Venue.venue_id
    ).order_by(models.Team.team_name.asc()).all()
    return templates.TemplateResponse(request, "user/view_teams.html", {"request": request, "teams": teams})

# View Squad players for a particular team
@app.get("/user/team_players", response_class=HTMLResponse)
def team_players(request: Request, team_id: int, db: Session = Depends(get_db)):
    team = db.query(models.Team).filter(models.Team.team_id == team_id).first()
    if not team:
        return RedirectResponse(url="/user/view_teams", status_code=status.HTTP_303_SEE_OTHER)
    
    players = db.query(models.Player).filter(models.Player.team_id == team_id).order_by(models.Player.player_name.asc()).all()
    
    batsmen = [p for p in players if p.role == 'Batsman']
    bowlers = [p for p in players if p.role == 'Bowler']
    all_rounders = [p for p in players if p.role == 'All-Rounder']
    wicketkeepers = [p for p in players if p.role == 'Wicketkeeper']
    
    return templates.TemplateResponse(request, "user/team_players.html", {
        "request": request, 
        "team": team, 
        "players": players,
        "batsmen": batsmen,
        "bowlers": bowlers,
        "all_rounders": all_rounders,
        "wicketkeepers": wicketkeepers,
        "Batsmen": batsmen,
        "Bowlers": bowlers,
        "All_Rounders": all_rounders,
        "Wicketkeepers": wicketkeepers
    })

# View Players Directory with filter capability
@app.get("/user/view_players", response_class=HTMLResponse)
def view_players(
    request: Request,
    role: str = "",
    team: str = "",
    name: str = "",
    db: Session = Depends(get_db)
):
    query = db.query(models.Player).join(models.Team)
    
    if role:
        query = query.filter(models.Player.role == role)
    if team:
        query = query.filter(models.Team.team_name == team)
    if name:
        query = query.filter(models.Player.player_name.like(f"%{name}%"))
        
    players = query.order_by(models.Player.player_name.asc()).all()
    all_teams = db.query(models.Team).order_by(models.Team.team_name.asc()).all()
    all_roles = [r[0] for r in db.query(models.Player.role).distinct().order_by(models.Player.role.asc()).all() if r[0]]
    
    return templates.TemplateResponse(request, "user/view_players.html", {
        "request": request,
        "players": players,
        "teams": all_teams,
        "roles": all_roles,
        "selectedRole": role,
        "selectedTeam": team,
        "nameFilter": name
    })

# View Match Summaries
@app.get("/user/view_match_summaries", response_class=HTMLResponse)
def view_match_summaries(request: Request, db: Session = Depends(get_db)):
    summaries = db.query(models.MatchSummary).join(models.Match).order_by(models.Match.match_date.desc()).all()
    return templates.TemplateResponse(request, "user/view_match_summaries.html", {
        "request": request, 
        "summaries": summaries
    })

# View Match Scorecard (Batting and Bowling details for both sides)
@app.get("/user/view_match_scorecard", response_class=HTMLResponse)
def view_match_scorecard(request: Request, match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).filter(models.Match.match_id == match_id).first()
    if not match:
        return RedirectResponse(url="/user/view_match_summaries", status_code=status.HTTP_303_SEE_OTHER)

    summary = db.query(models.MatchSummary).filter(models.MatchSummary.match_id == match_id).first()
    scorecard_entries = db.query(models.Scorecard).filter(models.Scorecard.match_id == match_id).all()
    
    team_scorecards = {
        match.team1_id: {'batsmen': [], 'bowlers': []},
        match.team2_id: {'batsmen': [], 'bowlers': []}
    }
    
    for entry in scorecard_entries:
        player = entry.player
        if not player:
            continue
            
        runs_scored = entry.runs or 0
        balls_faced = entry.balls_faced_batting or 0
        strike_rate = f"{(runs_scored / balls_faced) * 100:.2f}" if balls_faced > 0 else "0.00"
        
        wickets = entry.wickets or 0
        runs_conceded = entry.runs_conceded or 0
        balls_bowled = entry.balls_bowled_bowling or 0
        overs_bowled = balls_to_overs(balls_bowled)
        economy_rate = calculate_economy_rate(runs_conceded, balls_bowled)
        
        team_id = player.team_id
        if team_id not in team_scorecards:
            team_scorecards[team_id] = {'batsmen': [], 'bowlers': []}
            
        if player.role in ['Batsman', 'All-Rounder', 'Wicketkeeper']:
            if runs_scored > 0 or balls_faced > 0:
                team_scorecards[team_id]['batsmen'].append({
                    'player_id': player.player_id,
                    'player_name': player.player_name,
                    'role': player.role,
                    'player_photo': player.player_photo,
                    'runs': runs_scored,
                    'balls_faced': balls_faced,
                    'strike_rate': strike_rate
                })
                
        if player.role in ['Bowler', 'All-Rounder']:
            if wickets > 0 or balls_bowled > 0 or runs_conceded > 0:
                team_scorecards[team_id]['bowlers'].append({
                    'player_id': player.player_id,
                    'player_name': player.player_name,
                    'role': player.role,
                    'player_photo': player.player_photo,
                    'wickets': wickets,
                    'runs_conceded': runs_conceded,
                    'overs_bowled': overs_bowled,
                    'economy_rate': economy_rate
                })
                
    for t_id in team_scorecards:
        team_scorecards[t_id]['batsmen'].sort(key=lambda x: (-x['runs'], x['player_name']))
        team_scorecards[t_id]['bowlers'].sort(key=lambda x: (-x['wickets'], float(x['economy_rate']) if x['economy_rate'] != '0.00' else 9999.0, x['player_name']))
        
    return templates.TemplateResponse(request, "user/view_match_scorecard.html", {
        "request": request,
        "match": match,
        "summary": summary,
        "team_scorecards": team_scorecards
    })

# Leaderboard (Points table with NRR calculation)
@app.get("/user/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request, db: Session = Depends(get_db)):
    # Calculate NRR and fetch team metrics
    # Same query logic as user/leaderboard.php
    teams = db.query(models.Team).all()
    leaderboard_data = []
    
    default_overs_per_innings = 20
    
    for t in teams:
        # Calculate total runs scored and conceded in matches they played
        total_runs_scored = 0
        total_runs_conceded = 0
        total_matches_played = 0
        
        # Query summaries for matches involving this team
        summaries = db.query(models.MatchSummary).join(models.Match).filter(
            or_(
                models.Match.team1_id == t.team_id,
                models.Match.team2_id == t.team_id
            )
        ).all()
        
        for s in summaries:
            total_matches_played += 1
            if s.match.team1_id == t.team_id:
                total_runs_scored += (s.team1_score or 0)
                total_runs_conceded += (s.team2_score or 0)
            else:
                total_runs_scored += (s.team2_score or 0)
                total_runs_conceded += (s.team1_score or 0)
        
        if total_matches_played == 0:
            nrr = 0.0
        else:
            overs_played = total_matches_played * default_overs_per_innings
            overs_bowled = total_matches_played * default_overs_per_innings
            
            run_rate_for = total_runs_scored / overs_played if overs_played > 0 else 0
            run_rate_against = total_runs_conceded / overs_bowled if overs_bowled > 0 else 0
            nrr = run_rate_for - run_rate_against
            
        leaderboard_data.append({
            "team_id": t.team_id,
            "team_name": t.team_name,
            "logo": t.logo,
            "wins": t.wins,
            "losses": t.losses,
            "draws": t.draws,
            "points": t.points,
            "nrr": nrr
        })
        
    # Sort leaderboard: points DESC, then NRR DESC
    leaderboard_data.sort(key=lambda x: (x["points"], x["nrr"]), reverse=True)
    
    # Format NRR to 3 decimal places for display
    for row in leaderboard_data:
        row["nrr_str"] = f"{row['nrr']:.3f}"
        
    return templates.TemplateResponse(request, "user/leaderboard.html", {
        "request": request, 
        "leaderboard_data": leaderboard_data
    })

# View Player Aggregate Stats (batting & bowling leaderboards)
@app.get("/user/view_player_stats", response_class=HTMLResponse)
def view_player_stats(
    request: Request,
    role: str = "",
    team: str = "",
    name: str = "",
    db: Session = Depends(get_db)
):
    # Fetch base stats group by player
    query = db.query(
        models.Player.player_id,
        models.Player.player_name,
        models.Player.role,
        models.Player.player_photo,
        models.Team.team_name,
        func.sum(models.Scorecard.runs).label("total_runs_scored"),
        func.sum(models.Scorecard.wickets).label("total_wickets_taken"),
        func.sum(models.Scorecard.runs_conceded).label("total_runs_conceded"),
        func.sum(models.Scorecard.balls_faced_batting).label("total_balls_faced_batting"),
        func.sum(models.Scorecard.balls_bowled_bowling).label("total_balls_bowled_bowling"),
        func.count(func.distinct(models.Scorecard.match_id)).label("num_matches_played")
    ).join(
        models.Scorecard, models.Player.player_id == models.Scorecard.player_id
    ).join(
        models.Team, models.Player.team_id == models.Team.team_id
    )
    
    if role:
        query = query.filter(models.Player.role == role)
    if team:
        query = query.filter(models.Team.team_name == team)
    if name:
        query = query.filter(models.Player.player_name.like(f"%{name}%"))
        
    query = query.group_by(
        models.Player.player_id,
        models.Player.player_name,
        models.Player.role,
        models.Player.player_photo,
        models.Team.team_name
    )
    
    results = query.all()
    
    batsmen_stats = []
    bowlers_stats = []
    
    for r in results:
        # Common
        common = {
            "player_id": r.player_id,
            "player_name": r.player_name,
            "role": r.role,
            "player_photo": r.player_photo,
            "team_name": r.team_name,
            "num_matches_played": r.num_matches_played or 0
        }
        
        # Batting Stats
        if r.role in ["Batsman", "All-Rounder", "Wicketkeeper"]:
            runs = r.total_runs_scored or 0
            balls_faced = r.total_balls_faced_batting or 0
            strike_rate = f"{(runs / balls_faced) * 100:.2f}" if balls_faced > 0 else "0.00"
            avg_runs_per_match = f"{runs / r.num_matches_played:.2f}" if r.num_matches_played > 0 else "0.00"
            
            batsmen_stats.append({
                **common,
                "runs": runs,
                "balls_faced": balls_faced,
                "strike_rate": strike_rate,
                "avg_runs_per_match": avg_runs_per_match
            })
            
        # Bowling Stats
        if r.role in ["Bowler", "All-Rounder"]:
            wickets = r.total_wickets_taken or 0
            runs_conceded = r.total_runs_conceded or 0
            balls_bowled = r.total_balls_bowled_bowling or 0
            overs_bowled = balls_to_overs(balls_bowled)
            economy_rate = calculate_economy_rate(runs_conceded, balls_bowled)
            avg_runs_conceded_per_match = f"{runs_conceded / r.num_matches_played:.2f}" if r.num_matches_played > 0 else "0.00"
            
            bowlers_stats.append({
                **common,
                "wickets": wickets,
                "runs_conceded": runs_conceded,
                "overs_bowled": overs_bowled,
                "economy_rate": economy_rate,
                "avg_runs_conceded_per_match": avg_runs_conceded_per_match
            })
            
    # Sort Batsmen: runs DESC, name ASC
    batsmen_stats.sort(key=lambda x: (-x["runs"], x["player_name"]))
    
    # Sort Bowlers: wickets DESC, economy rate ASC, name ASC
    def bowler_sort_key(b):
        try:
            econ = float(b["economy_rate"])
        except ValueError:
            econ = 999.99
        return (-b["wickets"], econ, b["player_name"])
        
    bowlers_stats.sort(key=bowler_sort_key)
    
    all_teams = db.query(models.Team).order_by(models.Team.team_name.asc()).all()
    
    return templates.TemplateResponse(request, "user/view_player_stats.html", {
        "request": request,
        "batsmen_stats": batsmen_stats,
        "bowlers_stats": bowlers_stats,
        "teams": all_teams,
        "roleFilter": role,
        "teamFilter": team,
        "nameFilter": name
    })
