# Grok-4 Powered Discord Bot

This is a powerful, multi-featured Discord bot powered by the Grok-4 AI model via the Samurai API. It's designed to be a highly interactive and helpful assistant, capable of conversation, using tools to perform tasks, and much more.

## Features

- **Intelligent Conversation:** Responds to direct messages and in designated channels without needing to be pinged.
- **Private Chat Sessions:** Use the `/start` command to create a private channel between you and the bot. The bot will even rename the channel based on the topic of your first message!
- **Public Channel Mode:** Use the `/setchat` command to allow the bot to participate in a public server channel.
- **Advanced AI Tools:**
  - **Web Search:** Can search the web to provide up-to-date information.
  - **Artifact Creation:** Can generate files, such as code snippets, essays, or configuration files, and upload them directly to the chat.
  - **Python Execution:** Can execute Python code in a sandboxed environment to perform calculations or scripting tasks.
- **Heavy Mode:** A `/heavy-mode` command that utilizes multiple AI agents for more comprehensive and detailed responses.
- **Custom Emoji Use:** The AI is instructed to use the custom emojis available in your server.
- **"Thinking..." Indicator:** Provides visual feedback so you know when the bot is processing your request.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a `.env` file:** In the root of the project, create a file named `.env`. This file will store your secret keys.

3.  **Add API Keys to `.env`:** Add your Discord Bot Token and Samurai API Key to the `.env` file like this:
    ```
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
    SAMURAI_API_KEY="YOUR_SAMURAI_API_KEY_HERE"
    ```
    
4.  **Install Dependencies:** Install the required Python libraries using pip.
    ```bash
    pip install -r requirements.txt
    ```

5.  **Run the Bot:**
    ```bash
    python main.py
    ```

## Usage

The bot primarily operates through slash commands and direct messages.

-   **/start:** Creates a new private text channel for you and the bot.
-   **/setchat:** Designates the current channel as a public chat where the bot will respond to all messages. (Requires admin/manage channel permissions).
-   **/unsetchat:** Removes the bot from a public chat channel.
-   **/heavy-mode [prompt]:** Engages the multi-agent system for a high-quality response to your prompt.
-   **Direct Messages:** Simply send a message to the bot in a DM to start a conversation.
