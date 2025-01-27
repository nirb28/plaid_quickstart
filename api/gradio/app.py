import os
import gradio as gr
import pandas as pd
from datetime import datetime, timedelta
from plaid.api import plaid_api
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from dotenv import load_dotenv
from plaid.model.country_code import CountryCode

# Load environment variables
load_dotenv()

class PlaidViewer:
    def __init__(self):
        configuration = Configuration(
            host="https://sandbox.plaid.com",
            api_key={
                'clientId': os.getenv('PLAID_CLIENT_ID'),
                'secret': os.getenv('PLAID_SECRET')
            }
        )
        api_client = ApiClient(configuration)
        self.client = plaid_api.PlaidApi(api_client)
        self.access_token = None

    def create_link_token(self):
        try:
            request = LinkTokenCreateRequest(
                products=[Products('transactions')],
                client_name='Plaid Gradio App',
                country_codes=[CountryCode('US')],
                user={'client_user_id': f'user-{datetime.now().timestamp()}'},
                language='en'
            )
            response = self.client.link_token_create(request)
            return response['link_token']
        except Exception as e:
            return f"Error: {str(e)}"

    def exchange_token(self, public_token):
        try:
            request = ItemPublicTokenExchangeRequest(public_token=public_token)
            response = self.client.item_public_token_exchange(request)
            self.access_token = response['access_token']
            return "Successfully connected account!"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_transactions(self):
        if not self.access_token:
            return pd.DataFrame(), "Please connect an account first"
        
        try:
            end_date = datetime.strptime('2024-04-10', '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=40)
            
            request = TransactionsGetRequest(
                access_token=self.access_token,
                start_date=start_date,
                end_date=end_date
            )
            response = self.client.transactions_get(request)
            transactions = response['transactions']
            df = pd.DataFrame(transactions)

            # the transactions in the response are paginated, so make multiple calls while increasing the offset to
            # retrieve all transactions
            while len(transactions) < response['total_transactions']:
                options = TransactionsGetRequestOptions()
                options.offset = len(transactions)

                request = TransactionsGetRequest(
                    access_token=self.access_token,
                    start_date=start_date,
                    end_date=end_date,
                    options=options
                )
                response = self.client.transactions_get(request)
                df.append(pd.DataFrame(response['transactions']))

            return df[['date', 'name', 'amount', 'category']], "Transactions retrieved successfully"
            #return df, "Transactions retrieved successfully"
        except Exception as e:
            return pd.DataFrame(), f"Error: {str(e)}"

def create_ui():
    plaid = PlaidViewer()

    def get_link():
        return plaid.create_link_token()

    def connect(token):
        return plaid.exchange_token(token)

    def fetch_transactions():
        df, msg = plaid.get_transactions()
        return df, msg

    with gr.Blocks(title="Plaid Transaction Viewer") as app:
        gr.Markdown("# Plaid Transaction Viewer")
        
        with gr.Row():
            link_btn = gr.Button("Get Link Token")
            link_output = gr.Textbox(label="Link Token")
        
        with gr.Row():
            token_input = gr.Textbox(label="Enter Public Token")
            connect_btn = gr.Button("Connect Account")
            connect_output = gr.Textbox(label="Connection Status")
        
        status = gr.Textbox(label="Status")
        transactions = gr.DataFrame(label="Transactions")

        link_btn.click(fn=get_link, outputs=link_output)
        connect_btn.click(fn=connect, inputs=token_input, outputs=connect_output)
        refresh_btn = gr.Button("Refresh Transactions")
        refresh_btn.click(fn=fetch_transactions, outputs=[transactions, status])

    return app

if __name__ == "__main__":
    demo = create_ui()
    demo.launch()