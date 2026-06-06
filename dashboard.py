from fastapi import FastAPI, Request, Form, HTTPException, Depends, Cookie, Header
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
import sqlite3, os, httpx, json, secrets
from dotenv import load_dotenv
import math

load_dotenv()
app = FastAPI()
app.state.user_cache = {} # Global cache to prevent rate limits

# Use absolute path for templates on WispByte
template_dir = os.path.join(os.getcwd(), "templates")
templates = Jinja2Templates(directory=template_dir)

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-key")
s = URLSafeTimedSerializer(SECRET_KEY)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

def get_db():
    conn = sqlite3.connect("database.sqlite", timeout=10)
    conn.row_factory = sqlite3.Row # Return results as dictionaries
    return conn

@app.get("/health")
async def health_check():
    return {"status": "operational", "bot_ready": hasattr(app.state, 'bot') and app.state.bot.is_ready()}

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
        avatar_url = f"https://cdn.discordavatars.com/avatars/{user['id']}/{user['avatar']}.png" if user.get('avatar') else "https://cdn.discordapp.com/embed/avatars/0.png"
        
        response = RedirectResponse("/dashboard")
        data_to_store = {"id": user['id'], "name": user['username'], "avatar": avatar_url, "access_token": token}
        signed_data = s.dumps(data_to_store)
        response.set_cookie(key="user_session", value=signed_data, httponly=True, max_age=3600, samesite='lax')
        response.delete_cookie("oauth_state")
        return response

@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={
        "client_id": CLIENT_ID
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user_session: str = Cookie(None)):
    bot = getattr(request.app.state, 'bot', None)
    user_data = None
    managed_guilds = {} 
    
    if user_session:
        try: 
            user_data = s.loads(user_session, max_age=3600)
            token = user_data.get("access_token")
            async with httpx.AsyncClient(timeout=5.0) as client:
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
            g_dict = dict(g)
            gid_str = g_dict['guildId']
            if gid_str in managed_guilds:
                discord_guild = bot.get_guild(int(gid_str)) if bot else None
                if discord_guild:
                    g_dict['channels'] = [{"id": str(c.id), "name": c.name} for c in discord_guild.text_channels]
                else:
                    g_dict['channels'] = []
                guilds.append(g_dict)

        # Use app-level cache
        cache = request.app.state.user_cache
        gids = list(managed_guilds.keys()) if managed_guilds else []
        
        if gids:
            placeholders = ','.join(['?'] * len(gids))
            raw_top_users = [dict(r) for r in db.execute(f"SELECT * FROM Users WHERE guildId IN ({placeholders}) ORDER BY level DESC, xp DESC LIMIT 20", gids).fetchall()]
            tickets_raw = [dict(r) for r in db.execute(f"SELECT * FROM Tickets WHERE guildId IN ({placeholders}) ORDER BY status DESC, openedAt DESC LIMIT 20", gids).fetchall()]
            responders = [dict(r) for r in db.execute(f"SELECT * FROM AutoResponders WHERE guildId IN ({placeholders})", gids).fetchall()]
            warnings_raw = [dict(r) for r in db.execute(f"SELECT * FROM Warnings WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC LIMIT 20", gids).fetchall()]
            apps_raw = [dict(r) for r in db.execute(f"SELECT * FROM Applications WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC LIMIT 20", gids).fetchall()]
        else:
            raw_top_users, tickets_raw, responders, warnings_raw, apps_raw = [], [], [], [], []
        
        top_users = []
        for u in raw_top_users:
            u_dict = dict(u)
            uid = u_dict['userId']
            if u_dict['username']:
                name, avatar = u_dict['username'], u_dict['avatar']
                cache[uid] = (name, avatar)
            else:
                name, avatar = await resolve_user(bot, uid, cache)
            u_dict['name'] = name
            u_dict['avatar'] = avatar
            top_users.append(u_dict)

        active_giveaways = [dict(r) for r in db.execute("SELECT * FROM Giveaways WHERE active = 1").fetchall()]
        tickets_raw = [dict(r) for r in db.execute(f"SELECT * FROM Tickets WHERE guildId IN ({placeholders}) ORDER BY status DESC, openedAt DESC LIMIT 20", gids).fetchall()] if gids else []
        tickets = []
        for t in tickets_raw:
            uname, _ = await resolve_user(bot, t['userId'], cache)
            t['userName'] = uname
            tickets.append(t)

        responders = [dict(r) for r in db.execute(f"SELECT * FROM AutoResponders WHERE guildId IN ({placeholders})", gids).fetchall()] if gids else []
        warnings_raw = [dict(r) for r in db.execute(f"SELECT * FROM Warnings WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC LIMIT 20", gids).fetchall()] if gids else []
        warnings = []
        for w in warnings_raw:
            uname, _ = await resolve_user(bot, w['userId'], cache)
            mname, _ = await resolve_user(bot, w['moderatorId'], cache)
            w['userName'] = uname
            w['modName'] = mname
            warnings.append(w)

        apps_raw = [dict(r) for r in db.execute(f"SELECT * FROM Applications WHERE guildId IN ({placeholders}) ORDER BY timestamp DESC LIMIT 20", gids).fetchall()] if gids else []
        apps = []
        for a in apps_raw:
            uname, _ = await resolve_user(bot, a['userId'], cache)
            a['userName'] = uname
            apps.append(a)

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "guilds": guilds, "managed_guilds": managed_guilds, "top_users": top_users, 
        "user_data": user_data, "giveaways": active_giveaways, "tickets": tickets,
        "responders": responders, "warnings": warnings, "applications": apps,
        "bot_stats": {
            "latency": round(bot.latency * 1000) if bot and not math.isnan(bot.latency) else 0,
            "guild_count": len(bot.guilds) if bot else 0
        }
    })

async def verify_admin(guild_id: str, user_session: str):
    if not user_session: return False
    try:
        user_data = s.loads(user_session, max_age=3600)
        token = user_data.get("access_token")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
            if resp.status_code != 200: return False
            for g in resp.json():
                if g.get("id") == guild_id and (int(g.get("permissions", 0)) & 0x8):
                    return True
    except: pass
    return False

@app.post("/action/send")
async def send_message(
    guildId: str = Form(...), 
    channelId: str = Form(...), 
    message: str = Form(...), 
    user_session: str = Cookie(None),
    x_api_key: str = Header(None, alias="X-API-Key")
):
    # Allow access if either valid user session OR valid API Key is provided
    authorized = False
    if x_api_key and x_api_key == os.getenv("CONSOLE_API_KEY"):
        authorized = True
    elif await verify_admin(guildId, user_session):
        authorized = True

    if not authorized:
        raise HTTPException(status_code=403, detail="Unauthorized access")

    bot = app.state.bot
    guild = bot.get_guild(int(guildId))
    if not guild: return {"error": "Guild not found"}
    channel = guild.get_channel(int(channelId))
    if not channel: return {"error": "Channel not found"}
    await channel.send(message)
    return {"message": "Message sent!"}

@app.post("/responder/add")
async def add_responder(guildId: str = Form(...), trigger: str = Form(...), response: str = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session): raise HTTPException(status_code=403)
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO AutoResponders (guildId, trigger, response) VALUES (?, ?, ?)", (guildId, trigger, response))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/responder/delete")
async def delete_responder(guildId: str = Form(...), trigger: str = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session): raise HTTPException(status_code=403)
    with get_db() as db:
        db.execute("DELETE FROM AutoResponders WHERE guildId = ? AND trigger = ?", (guildId, trigger))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.post("/economy/update")
async def update_economy(guildId: str = Form(...), userId: str = Form(...), coins: int = Form(...), user_session: str = Cookie(None)):
    if not await verify_admin(guildId, user_session): raise HTTPException(status_code=403)
    with get_db() as db:
        db.execute("UPDATE Users SET coins = ? WHERE guildId = ? AND userId = ?", (coins, guildId, userId))
        db.commit()
    return RedirectResponse("/", status_code=303)

@app.get("/ticket/{ticket_id}/messages")
async def get_ticket_messages(ticket_id: int, user_session: str = Cookie(None)):
    if not user_session: raise HTTPException(status_code=403)
    with get_db() as db:
        messages = db.execute("SELECT authorName, content, timestamp FROM TicketMessages WHERE ticketId = ? ORDER BY timestamp ASC", (ticket_id,)).fetchall()
    return [{"author": m['authorName'], "content": m['content'], "time": m['timestamp']} for m in messages]

@app.post("/update")
async def update_settings(
    guildId: str = Form(...), autoMod: bool = Form(False), welcomeChannel: str = Form(None), 
    logChannel: str = Form(None), autoRole: str = Form(None), suggestionChannel: str = Form(None),
    ticketCategory: str = Form(None), ticketLogChannel: str = Form(None), staffRole: str = Form(None),
    themeColor: str = Form("#3498DB"), appReviewChannel: str = Form(None), appQuestions: str = Form("[]"), 
    bannedWords: str = Form("[]"), user_session: str = Cookie(None)
):
    if not await verify_admin(guildId, user_session): raise HTTPException(status_code=403)
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
