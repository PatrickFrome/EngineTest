# Coder backend

Stage B treats Coder as a persistent self-hosted workspace/control plane. The deterministic path uses the stable `coder ssh <workspace> -- <command>` CLI. Coder's built-in MCP server can be enabled separately for chat-native workspace management, but it is not required for candidate verification and never carries canonical Supabase authority.

Configure a pre-provisioned workspace name and access URL outside the repository. Remote Coder endpoints are classified as external and therefore cannot receive P3 tasks.
