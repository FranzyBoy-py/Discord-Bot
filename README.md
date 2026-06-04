# Franzy_Bot | Elite Discord Management System

A professional-grade Discord bot with a high-performance web dashboard, advanced economy system, AI integration, and robust moderation tools.

## 🚀 Features

### 🖥️ High-Performance Dashboard
- **Responsive Design:** Fully mobile-friendly interface with collapsible navigation.
- **Server Management:** Update bot settings, broadcast messages, and manage triggers in real-time.
- **Visual Control:** Manage tickets, applications, and server economy directly from the web.
- **OAuth2 Security:** Secure login via Discord with state-verified CSRF protection.

### 💰 Advanced Economy System
- **Daily Rewards & Work:** Engaging ways for users to earn coins.
- **Stable Ledger:** Robust SQLite database with explicit indexing for data integrity.
- **Leaderboards:** Global and server-specific rankings.

### 🛡️ Robust Moderation & Security
- **Anti-Spam:** Automatic detection and timeout for spamming members.
- **Banned Words:** Configurable word filters with automatic message deletion.
- **Audit Logs:** Comprehensive logging of all moderation actions.
- **Starboard:** Community-driven highlighting of the best messages.

### 🎵 Multimedia & AI
- **Music System:** High-quality audio streaming with queue management and autocompletion.
- **AI Integration:** Powered by Google Gemini for intelligent interactions and utilities.

## 🛠️ Setup & Installation

### Prerequisites
- Python 3.8+
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- A Google API Key (for AI features)
- Discord OAuth2 Credentials (for the Dashboard)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd "Public Discord Bot"
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables:
   Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token
   GOOGLE_API_KEY=your_google_ai_key
   SECRET_KEY=your_dashboard_secret_key
   DISCORD_CLIENT_ID=your_client_id
   DISCORD_CLIENT_SECRET=your_client_secret
   DISCORD_REDIRECT_URI=http://localhost:8000/callback
   ```
4. Run the bot:
   ```bash
   python bot.py
   ```

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! Feel free to check the issues page.
