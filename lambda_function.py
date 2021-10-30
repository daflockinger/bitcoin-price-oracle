import json
import boto3
import os
import json
import math
import datetime
from botocore.vendored import requests

runtime= boto3.client('runtime.sagemaker')

def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'headers' : { 'Content-Type' : 'application/json', 'Access-Control-Allow-Origin' : '*' },
        'body': json.dumps(create_prediction_response())
    }

def create_prediction_response():
    """Fetches the latest BTC prices, makes a prediction and returns the formated response as JSON"""

    days_of_prices = 60
    latest_prices = get_latest_btc_prices(days_of_prices)
    inference_request = create_inference_request(latest_prices)

    response = runtime.invoke_endpoint(EndpointName='forecasting-deepar-2021-10-29-06-44-53-190',
                                       ContentType='application/json',
                                       Body=inference_request)
    response_json = json.loads(response['Body'].read().decode('utf-8'))
    
    return format_response(response_json, latest_prices)
    
def get_latest_btc_prices(days_of_prices): 
    """Fetches the latest daily Bitcoin prices up to days_of_prices days in the past.

        Parameters
        ----------
        days_of_prices : int
            Number of days in the past, to fetch BTC prices from. 
    """

    response = requests.get('https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit={}'.format(days_of_prices - 1))
    json_prices = json.loads(response.text)
    return [ ( (json_price['high'] + json_price['low']) / 2 )  for json_price in json_prices['Data']['Data'] ]

def create_inference_request(latest_prices):
    """Creates the inference request payload for the predictor from the latest price data.

        Parameters
        ----------
        latest_prices : time series
            Time seris of daily bitcoin prices.
    """

    ts_start_timestamp = datetime.datetime.now() - datetime.timedelta(days=len(latest_prices))
    return json.dumps({ 
        "instances": [ { "start": ts_start_timestamp.strftime("%Y-%m-%d %H:%M:%S"), "target": latest_prices } ],
        "configuration": { "num_samples": 50, "output_types": ["mean", "quantiles", "samples"], "quantiles": ["0.1", "0.5", "0.9"] }
    })
    
def format_response(response, latest_prices): 
    """Formats the predictions and the latest prices so that the frontend can easily display it.

        Parameters
        ----------
        response : predictions
            Prediction results including mean prices and quantiles. 
        latest_prices : time series
            Time seris of daily bitcoin prices.
    """

    mean_predictions = response['predictions'][0]['mean']
    quantile_10 = response['predictions'][0]['quantiles']['0.1']
    quantile_90 = response['predictions'][0]['quantiles']['0.9']
    now = datetime.datetime.now()
    historic_days = len(latest_prices)
    prediction_days = len(mean_predictions)
    
    # add past prices
    historic_timestamps = [(now - datetime.timedelta(days=historic_days - days)).strftime("%Y-%m-%d") for days in range(historic_days)]
    formated_response = [ {'x': historic_timestamps[day], 'y': latest_prices[day], 'group': 'historic'}  for day in range(historic_days)]
    
    # added latest actual price as prediction to have a nicer connection from current price to predictions in the graph
    formated_response.append({'x': historic_timestamps[historic_days-1], 'y': latest_prices[historic_days-1], 'group': 'pred_median'})
    
    # add predictions with quantiles
    prediction_timestamps = [(now + datetime.timedelta(days=days)).strftime("%Y-%m-%d") for days in range(prediction_days)]
    for day in range(prediction_days):
        formated_response.append({'x': prediction_timestamps[day], 'y': mean_predictions[day], 'group': 'pred_median'})
    for day in range(prediction_days):
        formated_response.append({'x': prediction_timestamps[day], 'y': quantile_10[day], 'group': 'pred_q10'})    
    for day in range(prediction_days):
        formated_response.append({'x': prediction_timestamps[day], 'y': quantile_90[day], 'group': 'pred_q90'})
    
    return formated_response
    

