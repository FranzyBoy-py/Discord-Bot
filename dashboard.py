from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
import sqlite3, os, httpx, json
from dotenv import load_dotenv
import math

load_dotenv()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
s = URLSafeTimedSerializer(SECRET_KEY)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

def get_db():
    return sqlite3.connect("database.sqlite")

async def resolve_user(bot, user_id, cache):
    if user_id in cache:
        return cache[user_id]
    try:
        user = bot.get_user(int(user_id))
        if not user:
            user = await bot.fetch_user(int(user_id))
        result = (user.name, str(user.display_avatar.url))
        cache[user_id] = result
        return result
    except:
        return f"User {user_id}", "https://cdn.discordapp.com/embed/avatars/0.png"

import secrets

@app.get("/login")
async def login():
    state = secrets.token_urlsafe(32)
    response = RedirectResponse(f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify+guilds&state={state}")
    response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=300)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse("/")
    response.delete_cookie("user_session")
    return response

@app.get("/callback")
async def callback(code: str, state: str = None, oauth_state: str = Cookie(None)):
    if not state or state != oauth_state:
        raise HTTPException(status_code=400, detail="Invalid state parameter.")
        
    async with httpx.AsyncClient() as client:
        token_resp = await client.post("https://discord.com/api/oauth2/token", data={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "grant_type": "authorization_code",
            "code": code, "redirect_uri": REDIRECT_URI
        })
        token_data = token_resp.json()
        token = token_data.get("access_token")
        
        user_resp = await client.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token}"})
        user = user_resp.json()
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        response = RedirectResponse("/")
        data_to_store = {"id": user['id'], "name": user['username'], "avatar": avatar_url, "access_token": token}
        signed_data = s.dumps(data_to_store)
        # Use samesite='Lax' for basic CSRF protection
        response.set_cookie(key="user_session", value=signed_data, httponly=True, max_age=3600, samesite='lax')
        response.delete_cookie("oauth_state")
        return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user_session: str = Cookie(None)):
    bot = getattr(request.app.state, 'bot', None)
    user_data = None
    managed_guilds = {} 
    user_cache = {} 
    
    if user_session:
        try: 
            user_data = s.loads(user_session, max_age=3600)
            token = user_data.get("access_token")
            async with httpx.AsyncClient() as client:
                resp = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    for g in resp.json():
                        perms = int(g.get("permissions", 0))
                        if (perms & 0x8):
                            if bot and bot.get_guild(int(g['id'])):
                                managed_guilds[g['id']] = g['name']
        except: pass
    
    with get_db() as db:
        if managed_guilds:
            for gid in managed_guilds.keys():
                db.execute("INSERT OR IGNORE INTO Guilds (guildId) VALUES (?)", (gid,))
            db.commit()

        all_guilds_data = db.execute("SELECT * FROM Guilds").fetchall()
        guilds = []
        for g in all_guilds_data:
            if g[0] in managed_guilds:
                discord_guild = bot.get_guild(int(g[0])) if bot else None
                channels = [{"id": str(c.id), "name": c.name} for c in discord_guild.text_channels] if discord_guild else []
                guilds.append(list(g) + [channels])


        # Global Stats & Economy Management
        placeholders = ','.join(['?'] * len(managed_guilds)) if managed_guilds else "''"
        gids = list(managed_guilds.keys()) if managed_guilds else []
        
        raw_top_users = db.execute(f"SELECT userId, level, xp, coins, username, avatar, guildId FROM Users WHERE guildId IN ({placeholders}) ORDER BY level DESC, xp DESC", gids).fetchall() if gids else []
        
        top_users = []
        for u in raw_top_users:
            uid, lvl, xp, coins, db_name, db_avatar, gid = u
            if db_name:
                name, avatar = db_name, db_avatar
                user_cache[uid] = (name, avatar)
            else:
                name, avatar = await resolve_user(bot, uid, user_cache)
            top_users.append({
                "id": uid, "level": lvl or 0, "xp": xp or 0, "coins": coins if coins is not None else 0, 
                "name": name, "avatar": avatar, "guild_id": gid
            })

        active_giveaways = db.execute("SELECT prize, endTime, guildId FROM Giveaways WHERE active = 1").fetchall()
        
        tickets_raw = db.execute(f"SELECT * FROM Tickets WHERE guildId IN ({placeholders}) ORDER BY status DESC, openedAt DESC", gids).fetchall() if gids else []
        tickets = []
        for t in tickets_raw:
            uname, _ = await resolve_user(bot, t[3], user_cache)
            tickets.append(list(t) + [uname])

        responders = db.execute(f"SELECT * FROM AutoResponders WHERE guildId IN ({placeholders})", gids).fetchall() if gids else []
        
        warnings_raw = db.execute(f"SELECT * FROM Warnings WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC LIMIT 50", gids).fetchall() if gids else []
        warnings = []
        for w in warnings_raw:
            uname, _ = await resolve_user(bot, w[2], user_cache)
            mname, _ = await resolve_user(bot, w[3], user_cache)
            warnings.append(list(w) + [uname, mname])

        apps_raw = db.execute(f"SELECT * FROM Applications WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC", gids).fetchall() if gids else []
        apps = []
        for a in apps_raw:
            uname, _ = await resolve_user(bot, a[2], user_cache)
            apps.append(list(a) + [uname])

    return templates.TemplateResponse(request=request, name="index.html", context={
        "guilds": guilds, "managed_guilds": managed_guilds, "top_users": top_users, 
        "user_data": user_data, "giveaways": active_giveaways, "tickets": tickets,
        "responders": responders, "warnings": warnings, "applications": apps,
        "bot_stats": {
            "latency": round(bot.latency * 1000) if bot and not math.isnan(bot.latency) else 0,
            "guild_count": len(bot.guilds) if bot else 0
        }
    })

async def verify_admin(guild_id: str, user_session: str):
    if not user_session:
        raise HTTPException(status_code=401, detail="Session missing.")
    try:
        user_data = s.loads(user_session, max_age=3600)
        token = user_data.get("access_token")
    except:
        raise HTTPException(status_code=401, detail="Invalid session.")

    async with httpx.AsyncClient() as client:
        resp = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to verify permissions.")
        
        for g in resp.json():
            if g.get("id") == guild_id and (int(g.get("permissions", 0)) & 0x8):
                return True
    return False

@app.post("/action/send")
async def send_message(guildId: str = Form(...), channelId: str = Form(...), message: str = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session):
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    bot = app.state.bot
    guild = bot.get_guild(int(guildId))
    if not guild: return {"error": "Guild not found"}
    channel = guild.get_channel(int(channelId))
    if not channel: return {"error": "Channel not found"}
    await channel.send(message)
    return {"message": "Message sent!"}

@app.post("/responder/add")
async def add_responder(guildId: str = Form(...), trigger: str = Form(...), response: str = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session):
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO AutoResponders (guildId, trigger, response) VALUES (?, ?, ?)", (guildId, trigger, response))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/responder/delete")
async def delete_responder(guildId: str = Form(...), trigger: str = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session):
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    with get_db() as db:
        db.execute("DELETE FROM AutoResponders WHERE guildId = ? AND trigger = ?", (guildId, trigger))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/economy/update")
async def update_economy(
    guildId: str = Form(...), 
    userId: str = Form(...), 
    coins: int = Form(...),
    user_session: str = Cookie(None)
):
    if not await verify_admin(guildId, user_session):
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    with get_db() as db:
        db.execute(
            "UPDATE Users SET coins = ? WHERE guildId = ? AND userId = ?", 
            (coins, guildId, userId)
        )
        db.commit()
        
    return RedirectResponse("/", status_code=303)

@app.get("/ticket/{ticket_id}/messages")
async def get_ticket_messages(ticket_id: int, user_session: str = Cookie(None)):
    if not user_session: raise HTTPException(status_code=403)
    # Note: Ideally check if user has access to this ticket's guild
    with get_db() as db:
        messages = db.execute("SELECT authorName, content, timestamp FROM TicketMessages WHERE ticketId = ? ORDER BY timestamp ASC", (ticket_id,)).fetchall()
    return [{"author": m[0], "content": m[1], "time": m[2]} for m in messages]

@app.post("/update")
async def update_settings(
    guildId: str = Form(...), autoMod: bool = Form(False), welcomeChannel: str = Form(None), 
    logChannel: str = Form(None), autoRole: str = Form(None), suggestionChannel: str = Form(None),
    ticketCategory: str = Form(None), ticketLogChannel: str = Form(None), staffRole: str = Form(None),
    themeColor: str = Form("#3498DB"), appReviewChannel: str = Form(None), appQuestions: str = Form("[]"), 
    bannedWords: str = Form("[]"), user_session: str = Cookie(None)
):
    if not await verify_admin(guildId, user_session):
        raise HTTPException(status_code=403, detail="Unauthorized.")
        
    def to_json_list(val):
        try:
            parsed = json.loads(val)
            return json.dumps(parsed) if isinstance(parsed, list) else "[]"
        except:
            items = [i.strip() for i in val.split("|" if "|" in val else ",") if i.strip()]
            return json.dumps(items)
    processed_app_questions = to_json_list(appQuestions)
    processed_banned_words = to_json_list(bannedWords)
    with get_db() as db:
        db.execute("""
            UPDATE Guilds SET autoModEnabled = ?, welcomeChannelId = ?, logChannelId = ?, autoRoleId = ?,
            suggestionChannelId = ?, ticketCategoryId = ?, ticketLogChannelId = ?, 
            staffRoleId = ?, themeColor = ?, appReviewChannelId = ?, bannedWords = ?, appQuestions = ? WHERE guildId = ?
        """, (int(autoMod), welcomeChannel, logChannel, autoRole, suggestionChannel, ticketCategory, ticketLogChannel, staffRole, themeColor, appReviewChannel, processed_banned_words, processed_app_questions, guildId))
        db.commit()
    return {"message": "Settings updated"}
