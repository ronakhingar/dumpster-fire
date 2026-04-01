#!/usr/bin/env python3
"""
Tradovate API Client for Futures Trading

Much simpler than IBKR - no Gateway, no VNC, no 2FA headaches.
Pure REST API + WebSocket for real-time data.

Official docs: https://api.tradovate.com/
"""

import os
import requests
import json
from datetime import datetime
from typing import Optional, Dict, List
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

class TradovateClient:
    """
    Tradovate API client for futures trading.

    Features:
    - REST API for orders, positions, account data
    - WebSocket for real-time market data (optional)
    - Session token management
    - Clean, modern API (unlike IBKR)
    """

    def __init__(self, api_key: str, api_secret: str, account_id: str, demo: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.demo = demo

        # API endpoints
        if demo:
            self.base_url = "https://demo.tradovateapi.com/v1"
            self.ws_url = "wss://demo.tradovateapi.com/v1/websocket"
        else:
            self.base_url = "https://live.tradovateapi.com/v1"
            self.ws_url = "wss://live.tradovateapi.com/v1/websocket"

        self.access_token = None
        self.session = requests.Session()

    def authenticate(self) -> bool:
        """
        Authenticate with Tradovate API.

        Returns access token that lasts 24 hours (way better than IBKR).
        """
        try:
            response = self.session.post(
                f"{self.base_url}/auth/accesstokenrequest",
                json={
                    "name": self.api_key,
                    "password": self.api_secret,
                    "appId": "dumpster-fire-trading",
                    "appVersion": "1.0",
                    "deviceId": "server-001"
                }
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("accessToken")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.access_token}"
                })
                print(f"✓ Authenticated with Tradovate (demo={self.demo})")
                return True
            else:
                print(f"✗ Authentication failed: {response.text}")
                return False

        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False

    def get_account(self) -> Optional[Dict]:
        """Get account information."""
        try:
            response = self.session.get(f"{self.base_url}/account/list")
            if response.status_code == 200:
                accounts = response.json()
                # Find the account matching our account_id
                for acc in accounts:
                    if str(acc.get("id")) == str(self.account_id):
                        return acc
                return accounts[0] if accounts else None
            return None
        except Exception as e:
            print(f"Error getting account: {e}")
            return None

    def get_positions(self) -> List[Dict]:
        """Get current positions."""
        try:
            response = self.session.get(
                f"{self.base_url}/position/list",
                params={"accountId": self.account_id}
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting positions: {e}")
            return []

    def get_orders(self) -> List[Dict]:
        """Get open orders."""
        try:
            response = self.session.get(
                f"{self.base_url}/order/list",
                params={"accountId": self.account_id}
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            print(f"Error getting orders: {e}")
            return []

    def get_contract_id(self, symbol: str) -> Optional[int]:
        """
        Get contract ID for a symbol (e.g., "MES" or "MNQ").

        Tradovate uses internal contract IDs.
        """
        try:
            response = self.session.get(
                f"{self.base_url}/contract/find",
                params={"name": symbol}
            )
            if response.status_code == 200:
                contract = response.json()
                return contract.get("id")
            return None
        except Exception as e:
            print(f"Error getting contract ID for {symbol}: {e}")
            return None

    def place_order(
        self,
        symbol: str,
        side: str,  # "Buy" or "Sell"
        quantity: int,
        order_type: str = "Market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Optional[Dict]:
        """
        Place an order.

        Args:
            symbol: Contract symbol (e.g., "MES", "MNQ")
            side: "Buy" or "Sell"
            quantity: Number of contracts
            order_type: "Market", "Limit", "Stop", "StopLimit"
            limit_price: For limit orders
            stop_price: For stop orders

        Returns:
            Order response dict or None if failed
        """
        try:
            contract_id = self.get_contract_id(symbol)
            if not contract_id:
                print(f"✗ Could not find contract ID for {symbol}")
                return None

            order_data = {
                "accountId": int(self.account_id),
                "action": side,
                "orderQty": quantity,
                "orderType": order_type,
                "contractId": contract_id
            }

            if limit_price:
                order_data["price"] = limit_price
            if stop_price:
                order_data["stopPrice"] = stop_price

            response = self.session.post(
                f"{self.base_url}/order/placeorder",
                json=order_data
            )

            if response.status_code == 200:
                order = response.json()
                print(f"✓ Order placed: {side} {quantity} {symbol} @ {order_type}")
                return order
            else:
                print(f"✗ Order failed: {response.text}")
                return None

        except Exception as e:
            print(f"✗ Error placing order: {e}")
            return None

    def place_bracket_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Optional[Dict]:
        """
        Place a bracket order (entry + stop + target).

        Much simpler than IBKR's bracket order system.
        """
        try:
            contract_id = self.get_contract_id(symbol)
            if not contract_id:
                return None

            # Tradovate uses OCO (One-Cancels-Other) for bracket orders
            bracket_data = {
                "accountId": int(self.account_id),
                "action": side,
                "orderQty": quantity,
                "orderType": "Limit",
                "price": entry_price,
                "contractId": contract_id,
                "brackets": [
                    {
                        "action": "Sell" if side == "Buy" else "Buy",
                        "orderType": "Stop",
                        "stopPrice": stop_loss
                    },
                    {
                        "action": "Sell" if side == "Buy" else "Buy",
                        "orderType": "Limit",
                        "price": take_profit
                    }
                ]
            }

            response = self.session.post(
                f"{self.base_url}/order/placeorder",
                json=bracket_data
            )

            if response.status_code == 200:
                print(f"✓ Bracket order placed: {side} {quantity} {symbol}")
                print(f"  Entry: ${entry_price:.2f}, Stop: ${stop_loss:.2f}, Target: ${take_profit:.2f}")
                return response.json()
            else:
                print(f"✗ Bracket order failed: {response.text}")
                return None

        except Exception as e:
            print(f"✗ Error placing bracket order: {e}")
            return None

    def cancel_order(self, order_id: int) -> bool:
        """Cancel an order."""
        try:
            response = self.session.post(
                f"{self.base_url}/order/cancelorder",
                json={"orderId": order_id}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Error canceling order: {e}")
            return False

    def close_position(self, symbol: str) -> Optional[Dict]:
        """Close all positions for a symbol."""
        try:
            positions = self.get_positions()

            for pos in positions:
                if pos.get("contractName") == symbol:
                    quantity = abs(pos.get("netPos", 0))
                    if quantity == 0:
                        continue

                    # Determine side (opposite of position)
                    side = "Sell" if pos.get("netPos") > 0 else "Buy"

                    return self.place_order(
                        symbol=symbol,
                        side=side,
                        quantity=quantity,
                        order_type="Market"
                    )

            return None
        except Exception as e:
            print(f"Error closing position: {e}")
            return None


# Initialize from environment variables
def create_client() -> Optional[TradovateClient]:
    """Create Tradovate client from environment variables."""
    api_key = os.getenv("TRADOVATE_API_KEY")
    api_secret = os.getenv("TRADOVATE_API_SECRET")
    account_id = os.getenv("TRADOVATE_ACCOUNT_ID")
    demo = os.getenv("TRADOVATE_DEMO", "true").lower() == "true"

    if not all([api_key, api_secret, account_id]):
        print("✗ Missing Tradovate credentials in environment")
        return None

    client = TradovateClient(api_key, api_secret, account_id, demo)

    if client.authenticate():
        return client

    return None


if __name__ == "__main__":
    # Test connection
    from dotenv import load_dotenv
    load_dotenv()

    client = create_client()
    if client:
        print("\n✓ Tradovate client initialized")

        account = client.get_account()
        if account:
            print(f"  Account: {account.get('name')}")
            print(f"  Balance: ${account.get('cashBalance', 0):,.2f}")

        positions = client.get_positions()
        print(f"  Positions: {len(positions)}")

        orders = client.get_orders()
        print(f"  Open orders: {len(orders)}")
