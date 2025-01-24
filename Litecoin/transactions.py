import requests
import time
import json
from decimal import Decimal
import qrcode
import os
from io import BytesIO

class Litecoin:
    def __init__(self, username, password):
        self.__user = username
        self.__password = password
        self.base_url = "http://127.0.0.1:9332/"
        

    def __request(self, method, params = None):
        
        if params is None:
            params = []
        payload = {
            "jsonrpc": "1.0",
            "id": "curltest",
            "method": method,
            "params": params
        }
        
        command = f"""
        curl --user {self.__user}:{self.__password} --data-binary '{json.dumps(payload)}' -H 'content-type: text/plain;' {self.base_url}
        """
        result = os.popen(command).read()
        return json.loads(result)

            
    def get_ltc_to_usd_price(self):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "litecoin",
            "vs_currencies": "usd"
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            ltc_price = data["litecoin"]["usd"]
            return float(ltc_price)
        except:
            return None
        
    def get_new_address(self, identifier = None, label = None):
        payload = {
            "jsonrpc": "1.0",
            "id": identifier,
            "method": "getnewaddress",
            "params": [label]
        }
        
        try:
            response = requests.post(self.base_url, json=payload, auth=(self.__user, self.__password))
            response.raise_for_status()
            data = response.json()
            return data.get("result")
        except:
            return None
    
    def create_qr_code(self, address, amount):
        payment_uri = f"litecoin:{address}?amount={amount}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        qr.add_data(payment_uri)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        return img_bytes

    def create_invoice(self, amount):
        
        ltc_price = self.get_ltc_to_usd_price()
        if not ltc_price:
            return None

        ltc_amount = amount / ltc_price
        ltc_amount = round(ltc_amount, 8)


        address = self.get_new_address()
        if not address:
            return None


        payment_qr = self.create_qr_code(address, ltc_amount)
        
        return address, payment_qr, ltc_amount

    def get_transaction(self, address, amount, min_confirmations = 1):
        
        response = self.__request("getreceivedbyaddress", [address, min_confirmations])
        amount_received = response.get("result", 0)
    
        
        if amount_received:
            if amount_received >= amount:
                return True
        
        response_all = self.__request("listtransactions", ["*", 10, 0])
        transactions = response_all.get("result", [])

        for tx in transactions:
            if tx.get("address") == address:
                if tx.get("confirmations", 0) >= 0:
                    if tx.get("amount", 0) >= amount:
                        return True


    def create_payout(self, amount, address):
        try:
            response = self.__request("sendtoaddress", [address, round(amount / self.get_ltc_to_usd_price(), 8)])
            
            if "result" in response and response["result"] != None:
                tx_id = response["result"]
                return {"status": "success", "txid": tx_id}
            else:
                error = response.get("error", {})
                return {"status": "failed", "error": error}
        except Exception as e:
            return {"status": "error", "error": str(e)}