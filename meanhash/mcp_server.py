from typing import Any, Optional, Dict
import httpx
import os
from mcp.server.fastmcp import FastMCP
from core import SemID
from blockchain_integration import BlockchainConnector, SemIDBlockchainDeployer

# Initialize FastMCP server
mcp = FastMCP("world_context_protocol")

# SemIDインスタンスをグローバルに作成（モデルロードを一度だけ）
semid_instance = SemID()
private_key = os.getenv("BLOCKCHAIN_PRIVATE_KEY")

# ブロックチェーンコネクタ（環境変数から設定）
blockchain_connector: Optional[BlockchainConnector] = None
deployer: Optional[SemIDBlockchainDeployer] = None

def get_blockchain_connector() -> BlockchainConnector:
    """Get or create blockchain connector from environment variables"""
    global blockchain_connector

    if blockchain_connector is None:
        rpc_url = "https://eth-sepolia.g.alchemy.com/v2/xCvVMlO5hVjJ6_w5uJ4EQjSZ0RKiI7ym"
        factory_address = "0x35B586834b11dCa235B1007Faa312AA523aB6802"

        if not rpc_url:
            raise ValueError("BLOCKCHAIN_RPC_URL environment variable not set")

        try:
            blockchain_connector = BlockchainConnector(
                rpc_url=rpc_url,
                private_key=private_key,
                factory_address=factory_address
            )
        except Exception as e:
            raise ValueError(f"Failed to connect to blockchain: {e}")

    return blockchain_connector

def get_deployer() -> SemIDBlockchainDeployer:
    """Get or create SemID blockchain deployer"""
    global deployer

    if deployer is None:
        connector = get_blockchain_connector()
        deployer = SemIDBlockchainDeployer(semid_instance, connector)

    return deployer


# ===== Blockchain Integration Tools =====

@mcp.tool()
def blockchain_status() -> Dict[str, Any]:
    """
    Get the current blockchain connection status and configuration.

    Returns:
        Dictionary containing connection status, chain info, and account details
    """
    try:
        connector = get_blockchain_connector()

        status = {
            "connected": connector.w3.is_connected(),
            "chain_id": connector.w3.eth.chain_id,
            "factory_configured": connector.factory_address is not None,
            "account_configured": connector.account is not None,
        }

        if connector.account:
            balance = connector.w3.from_wei(
                connector.w3.eth.get_balance(connector.account.address), 'ether'
            )
            status.update({
                "account_address": connector.account.address,
                "account_balance": float(balance),
            })

        if connector.factory_address:
            status["factory_address"] = connector.factory_address

        return status

    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }


@mcp.tool()
def predict_contract_address(text: str) -> Dict[str, Any]:
    """
    Predict the contract address that would be deployed for the given text using SemID.

    Args:
        text: Input text to generate SemID and predict address for

    Returns:
        Dictionary containing SemID info and predicted contract address
    """
    try:
        connector = get_blockchain_connector()

        # Generate SemID and convert to 32-byte salt
        semid_value = semid_instance.id24(text)
        salt = semid_value.to_bytes(32, 'big')

        predicted_address = connector.compute_address(salt)
        is_deployed = connector.is_contract_deployed(predicted_address)

        return {
            "text": text,
            "semid": semid_value,
            "semid_hex": semid_instance.id_hex(text),
            "salt": salt.hex(),
            "predicted_address": predicted_address,
            "is_deployed": is_deployed
        }

    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def knowlege_mining(
    text: str,
    data: Optional[str] = "",
    decode_info: Optional[str] = "",
    arbitrary_info: Optional[str] = "",
    gas_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate SemID from text and deploy a KnowledgeContract using Create2.

    Args:
        text: Input text to generate SemID for deployment
        data: Hex-encoded binary data to store in contract (optional)
        decode_info: String describing how to decode the data (optional)
        arbitrary_info: Additional string info (optional, uses text if empty)
        gas_limit: Gas limit for deployment transaction (optional)

    Returns:
        Dictionary containing deployment result information
    """
    try:
        deployer_instance = get_deployer()

        # Convert hex data to bytes if provided
        data_bytes = bytes.fromhex(data) if data else b""

        result = deployer_instance.deploy_from_text(
            text=text,
            data=data_bytes,
            decode_info=decode_info,
            arbitrary_info=arbitrary_info,
            gas_limit=gas_limit
        )

        return result

    except Exception as e:
        return {"error": str(e)}



@mcp.tool()
def find_contract_by_text(text: str) -> Dict[str, Any]:
    """
    Find an existing KnowledgeContract deployed with the SemID of the given text.

    Args:
        text: Input text to find contract for

    Returns:
        Dictionary containing contract info if found, or deployment prediction if not found
    """
    try:
        connector = get_blockchain_connector()

        # Generate SemID and predict address
        semid_value = semid_instance.id24(text)
        salt = semid_value.to_bytes(32, 'big')
        predicted_address = connector.compute_address(salt)

        # Check if contract exists
        if connector.is_contract_deployed(predicted_address):
            # Get contract info
            contract_info = connector.get_contract_info(predicted_address)
            return {
                "found": True,
                "text": text,
                "semid": semid_value,
                "semid_hex": semid_instance.id_hex(text),
                "contract_address": predicted_address,
                "contract_info": contract_info
            }
        else:
            return {
                "found": False,
                "text": text,
                "semid": semid_value,
                "semid_hex": semid_instance.id_hex(text),
                "predicted_address": predicted_address,
                "message": "Contract not found. Use deploy_contract_from_text to deploy it."
            }

    except Exception as e:
        return {"error": str(e)}



if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')