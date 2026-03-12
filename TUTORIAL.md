---
title: "Build a OutlookMail agent with LangChain (TypeScript) and Arcade"
slug: "ts-langchain-OutlookMail"
framework: "langchain-ts"
language: "typescript"
toolkits: ["OutlookMail"]
tools: []
difficulty: "beginner"
generated_at: "2026-03-12T01:34:15Z"
source_template: "ts_langchain"
agent_repo: ""
tags:
  - "langchain"
  - "typescript"
  - "outlookmail"
---

# Build a OutlookMail agent with LangChain (TypeScript) and Arcade

In this tutorial you'll build an AI agent using [LangChain](https://js.langchain.com/) with [LangGraph](https://langchain-ai.github.io/langgraphjs/) in TypeScript and [Arcade](https://arcade.dev) that can interact with OutlookMail tools — with built-in authorization and human-in-the-loop support.

## Prerequisites

- The [Bun](https://bun.com) runtime
- An [Arcade](https://arcade.dev) account and API key
- An OpenAI API key

## Project Setup

First, create a directory for this project, and install all the required dependencies:

````bash
mkdir outlookmail-agent && cd outlookmail-agent
bun install @arcadeai/arcadejs @langchain/langgraph @langchain/core langchain chalk
````

## Start the agent script

Create a `main.ts` script, and import all the packages and libraries. Imports from 
the `"./tools"` package may give errors in your IDE now, but don't worry about those
for now, you will write that helper package later.

````typescript
"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";
````

## Configuration

In `main.ts`, configure your agent's toolkits, system prompt, and model. Notice
how the system prompt tells the agent how to navigate different scenarios and
how to combine tool usage in specific ways. This prompt engineering is important
to build effective agents. In fact, the more agentic your application, the more
relevant the system prompt to truly make the agent useful and effective at
using the tools at its disposal.

````typescript
// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['OutlookMail'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = "# Agent Prompt for Outlook Mail ReAct Agent\n\n## Introduction\nYou are an AI ReAct agent that helps users manage Outlook Mail. You can list, search, compose, draft, update, reply to, and send emails using the provided tools. Follow the ReAct pattern: think, act (call a tool), observe the tool result, then think again and either call another tool or produce the user-facing response.\n\n---\n\n## Instructions\n- Always follow the ReAct loop:\n  1. Thought: explain your reasoning briefly (one or two sentences).\n  2. Action: call the appropriate tool with exact parameters.\n  3. Observation: record the result returned by the tool.\n  4. Thought: decide next action or produce a final reply to the user.\n\n- Confirm destructive/irreversible actions when appropriate:\n  - OutlookMail_CreateAndSendEmail sends immediately \u2014 ask for explicit confirmation if the user intent is ambiguous.\n  - OutlookMail_SendDraftEmail will send an existing draft \u2014 confirm when user intent is not explicit.\n\n- Validate parameters before acting:\n  - Ensure email addresses are syntactically valid when adding recipients.\n  - Ensure required fields are present (e.g., message_id for replies/draft operations).\n  - If choosing a folder listing, provide exactly one of `well_known_folder_name` or `folder_id`.\n\n- Pagination and limits:\n  - Max `limit` is 100. If more results may be needed, use `pagination_token` from the observation to fetch additional pages.\n  - If the user asks for \"all\" messages, fetch iteratively until no pagination token remains (or until a safe maximum you define).\n\n- Prefer clarity and safety:\n  - Ask clarifying questions when the user intent is ambiguous (e.g., \"send now or save as draft?\", \"reply to sender only or reply-all?\").\n  - When updating drafts, clearly state which recipients will be added/removed before sending.\n\n- Use OutlookMail_WhoAmI when:\n  - You need to confirm the authenticated user\u0027s email address, mailbox settings, or auto-reply status.\n  - The user asks for account-related details.\n\n- Error handling:\n  - If a tool returns no results or an error (e.g., invalid message_id), inform the user and suggest corrective steps (e.g., search by subject/from/date).\n  - If a tool returns unexpected output, log the observation and ask the user whether to retry or refine the search.\n\n- Body content:\n  - Default `body_type` is \"text\". If the user requests rich content or HTML, set `body_type` to \"html\".\n\n---\n\n## Workflows\nBelow are common workflows and the specific sequence of tool calls the agent should use. For each workflow, follow the ReAct loop (Thought \u2192 Action \u2192 Observation \u2192 Thought \u2192 ...).\n\n1) Send a new email (send immediately)\n- Sequence:\n  - Confirm recipients/subject/body if not provided.\n  - OutlookMail_CreateAndSendEmail\n- Example:\n  ```\n  Thought: The user wants to send an email now.\n  Action: OutlookMail_CreateAndSendEmail\n  {\n    \"subject\": \"Project update\",\n    \"body\": \"Hi team,\\nHere is the status update...\",\n    \"to_recipients\": [\"alice@example.com\",\"bob@example.com\"],\n    \"cc_recipients\": [\"pm@example.com\"],\n    \"body_type\": \"text\"\n  }\n  Observation: {...}\n  Thought: Email sent. Inform user of success.\n  ```\n\n2) Create a draft (save without sending)\n- Sequence:\n  - Confirm recipients/subject/body if not provided.\n  - OutlookMail_CreateDraftEmail\n- Example:\n  ```\n  Thought: Save this as a draft for later editing.\n  Action: OutlookMail_CreateDraftEmail\n  {\n    \"subject\": \"Draft: Budget Q2\",\n    \"body\": \"Initial notes...\",\n    \"to_recipients\": [\"finance@example.com\"]\n  }\n  Observation: {...}\n  Thought: Return draft id and next steps.\n  ```\n\n3) List recent emails in a folder (e.g., Inbox)\n- Sequence:\n  - OutlookMail_ListEmailsInFolder\n  - If more pages needed, repeat with `pagination_token`.\n- Example:\n  ```\n  Thought: List the 10 newest emails in the Inbox.\n  Action: OutlookMail_ListEmailsInFolder\n  {\n    \"well_known_folder_name\": \"Inbox\",\n    \"limit\": 10\n  }\n  Observation: {..., \"nextPaginationToken\": \"...\"}\n  Thought: Show summaries or ask which message to act on.\n  ```\n\n4) List emails across the mailbox (no folder filter)\n- Sequence:\n  - OutlookMail_ListEmails\n- Example:\n  ```\n  Action: OutlookMail_ListEmails\n  {\n    \"limit\": 20\n  }\n  ```\n\n5) Search emails by property (subject, from, hasAttachments, importance, isRead, etc.)\n- Sequence:\n  - OutlookMail_ListEmailsByProperty\n  - Use pagination if necessary\n- Example searches:\n  ```\n  Action: OutlookMail_ListEmailsByProperty\n  {\n    \"property\": \"subject\",\n    \"operator\": \"contains\",\n    \"value\": \"invoice\",\n    \"limit\": 25\n  }\n  ```\n  or\n  ```\n  Action: OutlookMail_ListEmailsByProperty\n  {\n    \"property\": \"from\",\n    \"operator\": \"eq\",\n    \"value\": \"alice@example.com\",\n    \"limit\": 50\n  }\n  ```\n\n6) Reply to an existing email (reply to sender or reply-all)\n- Sequence:\n  - If message_id unknown: use listing/search workflows to locate message and get message_id.\n  - Ask whether to reply only to sender or all recipients if not provided.\n  - OutlookMail_ReplyToEmail\n- Example:\n  ```\n  Thought: Reply to the message with id 123.\n  Action: OutlookMail_ReplyToEmail\n  {\n    \"message_id\": \"123\",\n    \"body\": \"Thanks for the update \u2014 I will follow up with details.\",\n    \"reply_type\": \"ReplyType.REPLY_ALL\"\n  }\n  Observation: {...}\n  Thought: Inform user reply sent.\n  ```\n\n7) Update a draft (modify subject/body/recipients)\n- Sequence:\n  - If message_id unknown: list drafts (ListEmails or ListEmailsInFolder for Drafts) to find id.\n  - OutlookMail_UpdateDraftEmail\n  - Optionally OutlookMail_SendDraftEmail if user asks to send\n- Example:\n  ```\n  Thought: Add a CC and update the body of draft id abc-456.\n  Action: OutlookMail_UpdateDraftEmail\n  {\n    \"message_id\": \"abc-456\",\n    \"body\": \"Updated body with more details.\",\n    \"cc_add\": [\"manager@example.com\"]\n  }\n  Observation: {...}\n  Thought: Confirm update; ask whether to send now.\n  ```\n\n8) Send an existing draft\n- Sequence:\n  - Ensure you have the draft `message_id`.\n  - OutlookMail_SendDraftEmail\n- Example:\n  ```\n  Action: OutlookMail_SendDraftEmail\n  {\n    \"message_id\": \"abc-456\"\n  }\n  ```\n\n9) Find account info / environment (Who am I)\n- Sequence:\n  - OutlookMail_WhoAmI\n- Use when you need to confirm the user\u0027s email address, mailbox locale, or settings.\n\n---\n\n## ReAct Example Conversation (format to use)\nUse this style for internal agent reasoning and actions:\n\n```\nThought: I should confirm the recipient addresses before sending.\nAction: OutlookMail_CreateDraftEmail\n{\n  \"subject\": \"Q1 Report\",\n  \"body\": \"Draft of Q1 report attached.\",\n  \"to_recipients\": [\"ceo@example.com\"]\n}\nObservation: { \"id\": \"draft-789\", \"status\": \"created\" }\nThought: Draft created. Ask the user if they\u0027d like me to send it now or add attachments.\n```\n\nIf the agent decides to send:\n\n```\nThought: The user confirmed they want to send the draft.\nAction: OutlookMail_SendDraftEmail\n{\n  \"message_id\": \"draft-789\"\n}\nObservation: { \"status\": \"sent\", \"message_id\": \"sent-001\" }\nThought: Email sent successfully. Notify the user.\n```\n\n---\n\n## Best Practices \u0026 Notes\n- Be concise in Thoughts (1\u20132 sentences).\n- Use Action blocks only to call tools (no extra explanation in Action).\n- After each tool call, interpret the Observation and continue the flow.\n- When adding/removing recipients with OutlookMail_UpdateDraftEmail, use the specific to_add/to_remove/cc_add/cc_remove/bcc_add/bcc_remove fields.\n- For reply_type use \"ReplyType.REPLY\" (sender only) or \"ReplyType.REPLY_ALL\".\n- For body content set \"body_type\": \"html\" if the message includes HTML; otherwise omit or set \"text\".\n- For folder listing, `well_known_folder_name` examples: \"Inbox\", \"SentItems\", \"Drafts\", \"Trash\".\n- When ambiguous, ask clarifying questions to avoid mistakes (especially before sending).\n\n---\n\nUse this prompt as the agent\u0027s instruction set and template for every interaction. The agent must always act within the ReAct loop and only call tools when required to accomplish the user\u0027s request.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";
````

Set the following environment variables in a `.env` file:

````bash
ARCADE_API_KEY=your-arcade-api-key
ARCADE_USER_ID=your-arcade-user-id
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5-mini
````

## Implementing the `tools.ts` module

The `tools.ts` module fetches Arcade tool definitions and converts them to LangChain-compatible tools using Arcade's Zod schema conversion:

### Create the file and import the dependencies

Create a `tools.ts` file, and add import the following. These will allow you to build the helper functions needed to convert Arcade tool definitions into a format that LangChain can execute. Here, you also define which tools will require human-in-the-loop confirmation. This is very useful for tools that may have dangerous or undesired side-effects if the LLM hallucinates the values in the parameters. You will implement the helper functions to require human approval in this module.

````typescript
import { Arcade } from "@arcadeai/arcadejs";
import {
  type ToolExecuteFunctionFactoryInput,
  type ZodTool,
  executeZodTool,
  isAuthorizationRequiredError,
  toZod,
} from "@arcadeai/arcadejs/lib/index";
import { type ToolExecuteFunction } from "@arcadeai/arcadejs/lib/zod/types";
import { tool } from "langchain";
import {
  interrupt,
} from "@langchain/langgraph";
import readline from "node:readline/promises";

// This determines which tools require human in the loop approval to run
const TOOLS_WITH_APPROVAL = ['OutlookMail_CreateAndSendEmail', 'OutlookMail_CreateDraftEmail', 'OutlookMail_ListEmails', 'OutlookMail_ListEmailsByProperty', 'OutlookMail_ListEmailsInFolder', 'OutlookMail_ReplyToEmail', 'OutlookMail_SendDraftEmail', 'OutlookMail_UpdateDraftEmail', 'OutlookMail_WhoAmI'];
````

### Create a confirmation helper for human in the loop

The first helper that you will write is the `confirm` function, which asks a yes or no question to the user, and returns `true` if theuser replied with `"yes"` and `false` otherwise.

````typescript
// Prompt user for yes/no confirmation
export async function confirm(question: string, rl?: readline.Interface): Promise<boolean> {
  let shouldClose = false;
  let interface_ = rl;

  if (!interface_) {
      interface_ = readline.createInterface({
          input: process.stdin,
          output: process.stdout,
      });
      shouldClose = true;
  }

  const answer = await interface_.question(`${question} (y/n): `);

  if (shouldClose) {
      interface_.close();
  }

  return ["y", "yes"].includes(answer.trim().toLowerCase());
}
````

Tools that require authorization trigger a LangGraph interrupt, which pauses execution until the user completes authorization in their browser.

### Create the execution helper

This is a wrapper around the `executeZodTool` function. Before you execute the tool, however, there are two logical checks to be made:

1. First, if the tool the agent wants to invoke is included in the `TOOLS_WITH_APPROVAL` variable, human-in-the-loop is enforced by calling `interrupt` and passing the necessary data to call the `confirm` helper. LangChain will surface that `interrupt` to the agentic loop, and you will be required to "resolve" the interrupt later on. For now, you can assume that the reponse of the `interrupt` will have enough information to decide whether to execute the tool or not, depending on the human's reponse.
2. Second, if the tool was approved by the human, but it doesn't have the authorization of the integration to run, then you need to present an URL to the user so they can authorize the OAuth flow for this operation. For this, an execution is attempted, that may fail to run if the user is not authorized. When it fails, you interrupt the flow and send the authorization request for the harness to handle. If the user authorizes the tool, the harness will reply with an `{authorized: true}` object, and the system will retry the tool call without interrupting the flow.

````typescript
export function executeOrInterruptTool({
  zodToolSchema,
  toolDefinition,
  client,
  userId,
}: ToolExecuteFunctionFactoryInput): ToolExecuteFunction<any> {
  const { name: toolName } = zodToolSchema;

  return async (input: unknown) => {
    try {

      // If the tool is on the list that enforces human in the loop, we interrupt the flow and ask the user to authorize the tool

      if (TOOLS_WITH_APPROVAL.includes(toolName)) {
        const hitl_response = interrupt({
          authorization_required: false,
          hitl_required: true,
          tool_name: toolName,
          input: input,
        });

        if (!hitl_response.authorized) {
          // If the user didn't approve the tool call, we throw an error, which will be handled by LangChain
          throw new Error(
            `Human in the loop required for tool call ${toolName}, but user didn't approve.`
          );
        }
      }

      // Try to execute the tool
      const result = await executeZodTool({
        zodToolSchema,
        toolDefinition,
        client,
        userId,
      })(input);
      return result;
    } catch (error) {
      // If the tool requires authorization, we interrupt the flow and ask the user to authorize the tool
      if (error instanceof Error && isAuthorizationRequiredError(error)) {
        const response = await client.tools.authorize({
          tool_name: toolName,
          user_id: userId,
        });

        // We interrupt the flow here, and pass everything the handler needs to get the user's authorization
        const interrupt_response = interrupt({
          authorization_required: true,
          authorization_response: response,
          tool_name: toolName,
          url: response.url ?? "",
        });

        // If the user authorized the tool, we retry the tool call without interrupting the flow
        if (interrupt_response.authorized) {
          const result = await executeZodTool({
            zodToolSchema,
            toolDefinition,
            client,
            userId,
          })(input);
          return result;
        } else {
          // If the user didn't authorize the tool, we throw an error, which will be handled by LangChain
          throw new Error(
            `Authorization required for tool call ${toolName}, but user didn't authorize.`
          );
        }
      }
      throw error;
    }
  };
}
````

### Create the tool retrieval helper

The last helper function of this module is the `getTools` helper. This function will take the configurations you defined in the `main.ts` file, and retrieve all of the configured tool definitions from Arcade. Those definitions will then be converted to LangGraph `Function` tools, and will be returned in a format that LangChain can present to the LLM so it can use the tools and pass the arguments correctly. You will pass the `executeOrInterruptTool` helper you wrote in the previous section so all the bindings to the human-in-the-loop and auth handling are programmed when LancChain invokes a tool.


````typescript
// Initialize the Arcade client
export const arcade = new Arcade();

export type GetToolsProps = {
  arcade: Arcade;
  toolkits?: string[];
  tools?: string[];
  userId: string;
  limit?: number;
}


export async function getTools({
  arcade,
  toolkits = [],
  tools = [],
  userId,
  limit = 100,
}: GetToolsProps) {

  if (toolkits.length === 0 && tools.length === 0) {
      throw new Error("At least one tool or toolkit must be provided");
  }

  // Todo(Mateo): Add pagination support
  const from_toolkits = await Promise.all(toolkits.map(async (tkitName) => {
      const definitions = await arcade.tools.list({
          toolkit: tkitName,
          limit: limit
      });
      return definitions.items;
  }));

  const from_tools = await Promise.all(tools.map(async (toolName) => {
      return await arcade.tools.get(toolName);
  }));

  const all_tools = [...from_toolkits.flat(), ...from_tools];
  const unique_tools = Array.from(
      new Map(all_tools.map(tool => [tool.qualified_name, tool])).values()
  );

  const arcadeTools = toZod({
    tools: unique_tools,
    client: arcade,
    executeFactory: executeOrInterruptTool,
    userId: userId,
  });

  // Convert Arcade tools to LangGraph tools
  const langchainTools = arcadeTools.map(({ name, description, execute, parameters }) =>
    (tool as Function)(execute, {
      name,
      description,
      schema: parameters,
    })
  );

  return langchainTools;
}
````

## Building the Agent

Back on the `main.ts` file, you can now call the helper functions you wrote to build the agent.

### Retrieve the configured tools

Use the `getTools` helper you wrote to retrieve the tools from Arcade in LangChain format:

````typescript
const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});
````

### Write an interrupt handler

When LangChain is interrupted, it will emit an event in the stream that you will need to handle and resolve based on the user's behavior. For a human-in-the-loop interrupt, you will call the `confirm` helper you wrote earlier, and indicate to the harness whether the human approved the specific tool call or not. For an auth interrupt, you will present the OAuth URL to the user, and wait for them to finishe the OAuth dance before resolving the interrupt with `{authorized: true}` or `{authorized: false}` if an error occurred:

````typescript
async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}
````

### Create an Agent instance

Here you create the agent using the `createAgent` function. You pass the system prompt, the model, the tools, and the checkpointer. When the agent runs, it will automatically use the helper function you wrote earlier to handle tool calls and authorization requests.

````typescript
const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});
````

### Write the invoke helper

This last helper function handles the streaming of the agent’s response, and captures the interrupts. When the system detects an interrupt, it adds the interrupt to the `interrupts` array, and the flow interrupts. If there are no interrupts, it will just stream the agent’s to your console.

````typescript
async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}
````

### Write the main function

Finally, write the main function that will call the agent and handle the user input.

Here the `config` object configures the `thread_id`, which tells the agent to store the state of the conversation into that specific thread. Like any typical agent loop, you:

1. Capture the user input
2. Stream the agent's response
3. Handle any authorization interrupts
4. Resume the agent after authorization
5. Handle any errors
6. Exit the loop if the user wants to quit

````typescript
async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));
````

## Running the Agent

### Run the agent

```bash
bun run main.ts
```

You should see the agent responding to your prompts like any model, as well as handling any tool calls and authorization requests.

## Next Steps

- Clone the [repository](https://github.com/arcade-agents/ts-langchain-OutlookMail) and run it
- Add more toolkits to the `toolkits` array to expand capabilities
- Customize the `systemPrompt` to specialize the agent's behavior
- Explore the [Arcade documentation](https://docs.arcade.dev) for available toolkits

