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
const systemPrompt = `# AI Email Agent Prompt

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

By following these workflows, the AI Email Agent can effectively assist users in managing their email tasks seamlessly.`;
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";

const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});



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

const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});

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