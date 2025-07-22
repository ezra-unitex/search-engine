import os

from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_TABLE = "search_engine"

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "products"
VECTOR_DIM = 1536

SOAP_URL_SANMAR = os.getenv("SOAP_URL_SANMAR")
SOAP_ID_SANMAR = os.getenv("SOAP_ID_SANMAR")
SOAP_PASSWORD_SANMAR = os.getenv("SOAP_PASSWORD_SANMAR")
SOAP_URL_EDWARDS = os.getenv("SOAP_URL_EDWARDS")
SOAP_ID_EDWARDS = os.getenv("SOAP_ID_EDWARDS")
SOAP_PASSWORD_EDWARDS = os.getenv("SOAP_PASSWORD_EDWARDS")


HEADERS = {'Content-Type': 'text/xml'}
SANMAR_SOAP_NAMESPACES = {
    'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
    'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/',
    'def': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/'
}

EDWARDS_SOAP_NAMESPACES = {
    'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
    'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/1.0.0/',
    'def': 'http://www.promostandards.org/WSDL/ProductDataService/1.0.0/SharedObjects/'
}