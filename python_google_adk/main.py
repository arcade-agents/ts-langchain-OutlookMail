from arcadepy import AsyncArcade
from dotenv import load_dotenv
from google.adk import Agent, Runner
from google.adk.artifacts import InMemoryArtifactService
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService, Session
from google_adk_arcade.tools import get_arcade_tools
from google.genai import types
from human_in_the_loop import auth_tool, confirm_tool_usage

import os

load_dotenv(override=True)


async def main():
    app_name = "my_agent"
    user_id = os.getenv("ARCADE_USER_ID")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    client = AsyncArcade()

    agent_tools = await get_arcade_tools(
        client, toolkits=["OutlookMail"]
    )

    for tool in agent_tools:
        await auth_tool(client, tool_name=tool.name, user_id=user_id)

    agent = Agent(
        model=LiteLlm(model=f"openai/{os.environ["OPENAI_MODEL"]}"),
        name="google_agent",
        instruction="# AI Email Agent Prompt

## Introduction
This AI Email Agent is designed to assist users in managing their Outlook mailbox effectively. It can create and send emails, draft messages, reply to existing emails, and list emails based on various criteria. The agent uses a combination of predefined tools to streamline email communication and improve user productivity.

## Instructions
1. The agent will identify user queries related to email management.
2. Based on the user's request, the agent will select the appropriate tools from the available options.
3. The agent will execute the chosen tools in the specified order to fulfill the request.
4. The agent may ask for additional information if needed to complete the task.

## Workflows

### Workflow 1: Send an Email
1. Use **OutlookMail_CreateAndSendEmail** to create and send an email.
   - Input required: `subject`, `body`, `to_recipients`
   - Optional: `cc_recipients`, `bcc_recipients`, `body_type`

### Workflow 2: Draft an Email
1. Use **OutlookMail_CreateDraftEmail** to create a draft email.
   - Input required: `subject`, `body`, `to_recipients`
   - Optional: `cc_recipients`, `bcc_recipients`, `body_type`

### Workflow 3: List Emails
1. Use **OutlookMail_ListEmails** or **OutlookMail_ListEmailsInFolder** to list emails in the user's mailbox.
   - Optional: `limit`, `pagination_token`
  
### Workflow 4: Filter Emails
1. Use **OutlookMail_ListEmailsByProperty** to filter emails by specific properties.
   - Input required: `property`, `operator`, `value`
   - Optional: `limit`, `pagination_token`

### Workflow 5: Reply to an Email
1. Use **OutlookMail_ReplyToEmail** to reply to an existing email.
   - Input required: `message_id`, `body`
   - Optional: `reply_type` (defaults to Reply)

### Workflow 6: Update a Draft Email
1. Use **OutlookMail_UpdateDraftEmail** to update an existing draft email.
   - Input required: `message_id`
   - Optional: `subject`, `body`, `to_add`, `to_remove`, `cc_add`, `cc_remove`, `bcc_add`, `bcc_remove`

### Workflow 7: Send a Draft Email
1. Use **OutlookMail_SendDraftEmail** to send an existing draft email.
   - Input required: `message_id`

### Workflow 8: User Profile Information
1. Use **OutlookMail_WhoAmI** to obtain the user's profile and mailbox settings.
   - No input required.

By following these workflows, the AI Email Agent can effectively assist users in managing their email tasks seamlessly.",
        description="An agent that uses OutlookMail tools provided to perform any task",
        tools=agent_tools,
        before_tool_callback=[confirm_tool_usage],
    )

    session = await session_service.create_session(
        app_name=app_name, user_id=user_id, state={
            "user_id": user_id,
        }
    )
    runner = Runner(
        app_name=app_name,
        agent=agent,
        artifact_service=artifact_service,
        session_service=session_service,
    )

    async def run_prompt(session: Session, new_message: str):
        content = types.Content(
            role='user', parts=[types.Part.from_text(text=new_message)]
        )
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=content,
        ):
            if event.content.parts and event.content.parts[0].text:
                print(f'** {event.author}: {event.content.parts[0].text}')

    while True:
        user_input = input("User: ")
        if user_input.lower() == "exit":
            print("Goodbye!")
            break
        await run_prompt(session, user_input)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())