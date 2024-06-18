#!/bin/bash 
set -e

client_secret=$CLIENT_SECRET

response=$(curl -s --request POST \
  --url https://dev-qfnm6uuqxtjs3l44.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data "{\"client_id\":\"DsfPLEIFU5Gn9qmhTuMnqiV8Irs3fUi3\",\"client_secret\":\"$client_secret\",\"audience\":\"https://testing.api\",\"grant_type\":\"client_credentials\"}")

echo $response