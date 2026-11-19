# agentcore-first-agent

A minimal Amazon Bedrock AgentCore agent you can deploy from your terminal. It is a
[Strands](https://strandsagents.com/) agent with one useful tool: it checks the public
AWS Health Dashboard feed and answers questions like "is anything broken in us-east-1
right now?"

Companion repo for the tutorial **"Deploying your first agent with AgentCore CLI."**

This was Tested with [agentcore-cli](https://github.com/aws/agentcore-cli) **v1.0.3**.

## Prerequisites

- Node.js 20.12 or later
- [uv](https://docs.astral.sh/uv/)
- AWS credentials configured as for the AWS CLI, with permissions to run CDK
  deployments and you will need AdministratorAccess, or PowerUser plus IAM role creation.
- Amazon Bedrock model access for Claude Haiku 4.5 in your region (the agent uses
  `us.anthropic.claude-haiku-4-5-20251001-v1:0`; change it in `app/agent/model/load.py`
  if your account has access to a different model)

Install the CLI, pinned to the version this repo was tested with:

```bash
npm install -g @aws/agentcore@1.0.3
```

## What's in here

```
agentcore/
  agentcore.json      # project spec: one runtime, one memory
  cdk/                # the CDK app `agentcore deploy` synthesizes and deploys
app/agent/
  main.py             # the agent: Strands and a custom tool to check_aws_health
  model/, memory/     # model loading and AgentCore Memory session wiring
```

The project was scaffolded with:

```bash
agentcore create --name FirstAgent --template agent-python-strands
```

## Run it locally

```bash
agentcore dev
```

Note the port in the "Agent 'agent' is running on port NNNN" line, then in a second
terminal:

```bash
agentcore invoke --runtime agent --local --port NNNN --payload '{"prompt": "Any AWS incidents right now?"}'
```

## Run the tests

The agent has a pytest suite for payload parsing, the health-check tool, and memory. You can simply run them by going into the app/agent directory and running them.

```bash
cd app/agent
uv run pytest
```

## Deploy

```bash
agentcore deploy
```

The first deploy records your account and region as the default target in
`agentcore/aws-targets.json` (gitignored here since it contains your account ID) and
creates the CDK bootstrap stack if the account/region doesn't have one. Everything is
CDK under the hood: rerunning `agentcore deploy` is idempotent and converges to what
`agentcore/agentcore.json` declares.

Check what got deployed:

```bash
agentcore status
```

## Invoke

```bash
agentcore invoke --runtime agent --payload '{"prompt": "Is S3 having issues in us-east-1?"}'
```

Logs and traces for the deployed agent:

```bash
agentcore logs --runtime agent
agentcore traces --runtime agent
```

## Cleanup

Empty the project spec, then deploy the (now empty) project to delete the stack:

```bash
agentcore remove all --yes
agentcore deploy --yes
```

Restore the project spec afterward with `git checkout agentcore/agentcore.json`.

The CDK bootstrap stack (`CDKToolkit`) is shared account infrastructure and is left
alone. Delete it manually only if nothing else in the account uses CDK.

## License

MIT
