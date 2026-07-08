from voxrelay_client import VoxRelayClient
client = VoxRelayClient(); client.login('agentmanager@voxrelay.demo'); versions = client.list_agent_versions(); print(versions)
