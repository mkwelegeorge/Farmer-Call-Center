from flask import Flask, jsonify
from flask_mysqldb import MySQL
from twilio.rest import Client
import boto3 
from botocore.client import Config
from gtts import gTTS
import os
import utils

from config import config
from farmers_log.search_user_request import search_log
from farmers_log.summarize_log import xlnet_summarizer
from utils import response_payload

from config import config, ACCESS_KEY_ID, ACCESS_SECRET_KEY, BUCKET_NAME


app = Flask(__name__)

conexion = MySQL(app)


#The thelephone number associated whit the twilio account is: 
# --------> +240222313788
# The titles of the topics stored in the database are:
    # Nutrition
    # Fertilizantes
    # Cultivation
    # Harvest

@app.route("/test", methods = ["GET"])
def test():
    return response_payload(True, "Hello World")

@app.route("/farmers-log", methods = ["POST"])
def farmers_log():
    data = request.get_json()
    if not data:
        return response_payload(False, msg="No data provided")
    log = data.get("log")
    if not log:
        return response_payload(False, msg="No log provided")
    summary = xlnet_summarizer(log)
    search_result = search_log(summary)
    return response_payload(True,search_result, "Success search")


@app.route('/find_response/<phone_number>/<message_body>', methods=['GET','POST'])
def find_response(phone_number,message_body):
    try:
        cursor=conexion.connection.cursor()
        sql="SELECT content FROM topics WHERE topic_title = '{0}'".format(message_body)
        cursor.execute(sql)
        resp=cursor.fetchone()
        if resp != None:
            response = resp[0]
            
            
            # Convert text to audio
            mytext = response
            languaje = "es"
            myobj = gTTS(text=mytext, lang=languaje, slow=False)
            myobj.save("response.mp3")   
            
            # Send the audio in to bucket
            s3 = boto3.resource(
            's3',
            aws_access_key_id = ACCESS_KEY_ID,
            aws_secret_access_key = ACCESS_SECRET_KEY,
            config=Config(signature_version='s3v4')
            )
            data = open('response.mp3', 'rb')
            s3.Bucket(BUCKET_NAME).put_object(Key='response.mp3', Body=data, ContentType='audio/mp3')      
            
            s3_url = f"https://{BUCKET_NAME}.s3.{'us-east-1'}.amazonaws.com/{'response.mp3'}"
            
            # Send sms
            def sms_response(phone_number,response, s3_url):
                account_sid = "ACa14fbcbce98e84a08d6a60bbdebbf18b"
                auth_token = "9a9bf0f756d4d38fcbb305e252c27f4a"

                
                client = Client(account_sid, auth_token)
                message = client.messages.create(
                    body = response + " " + "Abra el siguiente enlace para escuchar la respuesta " +  s3_url,
                    from_ = "+19452392171", 
                    to = phone_number        
                )
            try:
                sms_response(phone_number, response, s3_url)
            except Exception as ex:
                return jsonify({'message':"Check your internet conection."})
            
                
            return jsonify({ 'Abra el siguiente enlace para escuchar la respuesta': s3_url,  'message':response,'topic':"Topic found."})
        else:    
            return jsonify({'message':"Topic not found."})
    except Exception as ex:
        return jsonify({'message':"Error"})
        


def page_not_found(error):
    return "<h1> Page not found ...", 404
      

if __name__ == '__main__':
    app.config.from_object(config['development'])
    app.register_error_handler(404, page_not_found)
    app.run()
    
    
    