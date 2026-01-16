from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["OutlookMail"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# AI Email Agent Prompt

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
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())