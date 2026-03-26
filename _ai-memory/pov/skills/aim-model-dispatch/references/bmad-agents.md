# BMAD Agent Reference

## Agent Command Reference

| Agent Type | Activation Command |
|---|---|
| Developer | `/bmad-agent-dev` |
| PM (Product Manager) | `/bmad-agent-pm` |
| Analyst | `/bmad-agent-analyst` |
| Architect | `/bmad-agent-architect` |
| Scrum Master | `/bmad-agent-sm` |
| QA Engineer | `/bmad-agent-qa` |
| UX Designer | `/bmad-agent-ux-designer` |
| Tech Writer | `/bmad-agent-tech-writer` |
| Quick Flow Solo Dev | `/bmad-agent-quick-flow-solo-dev` |
| Agent Builder | `/bmad-agent-builder` |
| Workflow Builder | `/bmad-workflow-builder` |
| Brainstorming Coach | `/bmad-cis-agent-brainstorming-coach` |
| Creative Problem Solver | `/bmad-cis-agent-creative-problem-solver` |
| Design Thinking Coach | `/bmad-cis-agent-design-thinking-coach` |
| Innovation Strategist | `/bmad-cis-agent-innovation-strategist` |
| Presentation Master | `/bmad-cis-agent-presentation-master` |
| Storyteller | `/bmad-cis-agent-storyteller` |
| Test Architect (TEA) | `/bmad-tea` |

## Task-to-Agent Selection Guide

When the task description does not specify an agent:

| Task Type | Agent | Menu Code |
|---|---|---|
| Research / analyze codebase | Analyst | Use menu |
| Create or update PRD | PM | `CP` |
| Validate a PRD | PM | `VP` |
| Break down features into stories | PM | `CE` |
| Design system architecture | Architect | Use menu |
| Sprint planning | SM | Use menu |
| Write code / implement a story | DEV | `DS` |
| Review implemented code | DEV | `CR` |
| Design user flows | UX Designer | Use menu |
| Write or review documentation | Tech Writer | `WD` |
| Validate documentation | Tech Writer | `VD` |
| Write and run tests | QA | Use menu |
| Build new BMAD agents | Agent Builder | Use menu |
| Build new BMAD workflows | Workflow Builder | Use menu |

## Direct Command to Agent Mapping

When the user specifies a direct workflow command, map it to two-phase activation:

| Direct Command | Activate Agent | Menu Code |
|---|---|---|
| `/bmad-code-review` | `/bmad-agent-dev` | `CR` |
| `/bmad-dev-story` | `/bmad-agent-dev` | `DS` |
| `/bmad-create-prd` | `/bmad-agent-pm` | `CP` |
| `/bmad-validate-prd` | `/bmad-agent-pm` | `VP` |
| `/bmad-create-epics-and-stories` | `/bmad-agent-pm` | `CE` |
| `/bmad-create-architecture` | `/bmad-agent-architect` | Use menu |
| `/bmad-sprint-planning` | `/bmad-agent-sm` | Use menu |
| `/bmad-create-ux-design` | `/bmad-agent-ux-designer` | Use menu |
