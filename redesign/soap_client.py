import requests, xml.etree.ElementTree as ET
from config import (SOAP_URL_SANMAR, SOAP_ID_SANMAR, SOAP_PASSWORD_SANMAR, HEADERS, SANMAR_SOAP_NAMESPACES, SOAP_ID_EDWARDS,
                    SOAP_PASSWORD_EDWARDS, SOAP_URL_EDWARDS, EDWARDS_SOAP_NAMESPACES)
from abc import ABC, abstractmethod

class BaseSOAPClient(ABC):

    @abstractmethod
    def get_sellable_product_ids(self):
        pass

    @abstractmethod
    def fetch_product_data(self, product_ids):
        pass


def get_client(impl_name="A") -> BaseSOAPClient:
    if impl_name == "sanmar":
        return SOAPClientSanMarImpl()
    elif impl_name == "edwards":
        return SOAPClientEdwardsImpl()
    else:
        raise ValueError(f"Unknown implementation: {impl_name}")


class SOAPClientSanMarImpl(BaseSOAPClient):
    def get_sellable_product_ids(self):
        # Implementation A
        payload = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/"
            xmlns:shar="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
            <soapenv:Header/>
            <soapenv:Body>
                <ns:GetProductSellableRequest>
                    <shar:wsVersion>2.0.0</shar:wsVersion>
                    <shar:id>{SOAP_ID_SANMAR}</shar:id>
                    <shar:password>{SOAP_PASSWORD_SANMAR}</shar:password>
                    <shar:isSellable>true</shar:isSellable>
                </ns:GetProductSellableRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        resp = requests.post(SOAP_URL_SANMAR + "?WSDL", headers=HEADERS, data=payload)
        root = ET.fromstring(resp.text)

        product_ids = set()
        for el in root.findall('.//ns2:ProductSellable', SANMAR_SOAP_NAMESPACES):
            id_el = el.find('.//def:productId', SANMAR_SOAP_NAMESPACES)
            if id_el is not None:
                product_ids.add(id_el.text)

        return list(product_ids)

    def fetch_product_data(self, product_id):
        payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
            xmlns:ns="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/" 
            xmlns:shar="http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/">
            <soapenv:Header/>
            <soapenv:Body>
                <ns:GetProductRequest>
                    <shar:wsVersion>2.0.0</shar:wsVersion>
                    <shar:id>{SOAP_ID_SANMAR}</shar:id>
                    <shar:password>{SOAP_PASSWORD_SANMAR}</shar:password>
                    <shar:localizationCountry>US</shar:localizationCountry>
                    <shar:localizationLanguage>en</shar:localizationLanguage>
                    <shar:productId>{product_id}</shar:productId>
                </ns:GetProductRequest>
            </soapenv:Body>
        </soapenv:Envelope>"""

        headers = {'Content-Type': 'text/xml'}

        try:
            resp = requests.post(SOAP_URL_SANMAR, headers=headers, data=payload)
            if resp.status_code != 200:
                print(f"[!] HTTP error for {product_id}: {resp.status_code}")
                return None

            xml_root = ET.fromstring(resp.text)

            # Namespaces for XML elements
            namespaces = {
                'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/',
                'def': 'http://www.promostandards.org/WSDL/ProductDataService/2.0.0/SharedObjects/'
            }

            product = xml_root.find('.//ns2:Product', namespaces)
            if product is None:
                print(f"[!] No product found in response for {product_id}")
                return None

            def get_text(elem, tag):
                e = elem.find(tag, namespaces)
                return e.text.strip() if e is not None and e.text else None

            product_id_val = get_text(product, 'def:productId')
            product_name = get_text(product, 'def:productName')
            product_brand = get_text(product, 'def:productBrand')
            image_url = get_text(product, 'def:primaryImageUrl')

            # Descriptions combined
            descriptions = [d.text.strip() for d in product.findall('def:description', namespaces) if d.text]
            combined_description = " ".join(descriptions)

            # Keywords
            keywords = []
            keyword_array = product.find('ns2:ProductKeywordArray', namespaces)
            if keyword_array is not None:
                for kw in keyword_array.findall('def:ProductKeyword/def:keyword', namespaces):
                    if kw.text:
                        keywords.append(kw.text.strip())

            # Categories and subcategories extraction
            categories = []
            product_categories = product.findall('ns2:ProductCategoryArray/def:ProductCategory', namespaces)
            for cat in product_categories:
                cat_name_el = cat.find('def:category', namespaces)
                sub_cat_el = cat.find('def:subCategory', namespaces)
                if cat_name_el is not None and cat_name_el.text:
                    categories.append(cat_name_el.text.strip())
                if sub_cat_el is not None and sub_cat_el.text:
                    # split comma separated subcategories and add individually
                    categories.extend([s.strip() for s in sub_cat_el.text.split(',')])

            # Product parts info
            colors = set()
            sizes = set()
            gtin = None
            flags = {}

            product_parts = product.findall('ns2:ProductPartArray/ns2:ProductPart', namespaces)
            for part in product_parts:
                primary_color = part.find('ns2:primaryColor/def:Color/def:standardColorName', namespaces)
                if primary_color is not None and primary_color.text:
                    colors.add(primary_color.text.strip())

                color_array = part.findall('ns2:ColorArray/def:Color/def:standardColorName', namespaces)
                for c in color_array:
                    if c.text:
                        colors.add(c.text.strip())

                apparel_size = part.find('def:ApparelSize', namespaces)
                if apparel_size is not None:
                    label_size = apparel_size.find('def:labelSize', namespaces)
                    if label_size is not None and label_size.text:
                        sizes.add(label_size.text.strip())

                gtin_el = part.find('def:gtin', namespaces)
                if gtin_el is not None and gtin_el.text:
                    gtin = gtin_el.text.strip()

                for flag_name in ['isRushService', 'isCloseout', 'isCaution', 'isOnDemand', 'isHazmat']:
                    flag_el = part.find(f'def:{flag_name}', namespaces)
                    if flag_el is not None and flag_el.text:
                        flags[flag_name] = flag_el.text.strip().lower() == 'true'

            product_data = {
                "product_id": product_id_val,
                "name": product_name,
                "brand": product_brand,
                "image_url": image_url,
                "description": combined_description,
                "keywords": keywords,
                "categories": categories,
                "colors": list(colors),
                "sizes": list(sizes),
                "gtin": gtin,
                "flags": flags
            }
            return product_data

        except Exception as e:
            print(f"[!] Exception for {product_id}: {e}")
            return None

class SOAPClientEdwardsImpl(BaseSOAPClient):
    def get_sellable_product_ids(self):
        # Implementation A
        payload = f"""
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns="http://www.promostandards.org/WSDL/Inventory/2.0.0/"
            xmlns:shar="http://www.promostandards.org/WSDL/Inventory/2.0.0/SharedObjects/">
            <soapenv:Header/>
            <soapenv:Body>
                <ns:GetProductSellableRequest>
                    <shar:wsVersion>1.0.0</shar:wsVersion>
                    <shar:id>{SOAP_ID_EDWARDS}</shar:id>
                    <shar:password>{SOAP_PASSWORD_EDWARDS}</shar:password>
                    <shar:isSellable>true</shar:isSellable>
                </ns:GetProductSellableRequest>
            </soapenv:Body>
        </soapenv:Envelope>
        """

        resp = requests.post(SOAP_URL_EDWARDS + "?WSDL", headers=HEADERS, data=payload)
        root = ET.fromstring(resp.text)

        product_ids = set()
        for el in root.findall('.//ns2:ProductSellable', EDWARDS_SOAP_NAMESPACES):
            id_el = el.find('.//def:productId', EDWARDS_SOAP_NAMESPACES)
            if id_el is not None:
                product_ids.add(id_el.text)

        return list(product_ids)

    def fetch_product_data(self, product_id):
        payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
            xmlns:ns="http://www.promostandards.org/WSDL/ProductDataService/1.0.0/" 
            xmlns:shar="http://www.promostandards.org/WSDL/ProductDataService/1.0.0/SharedObjects/">
            <soapenv:Header/>
            <soapenv:Body>
                <ns:GetProductRequest>
                    <shar:wsVersion>1.0.0</shar:wsVersion>
                    <shar:id>{SOAP_ID_EDWARDS}</shar:id>
                    <shar:password>{SOAP_PASSWORD_EDWARDS}</shar:password>
                    <shar:localizationCountry>US</shar:localizationCountry>
                    <shar:localizationLanguage>en</shar:localizationLanguage>
                    <shar:productId>{product_id}</shar:productId>
                </ns:GetProductRequest>
            </soapenv:Body>
        </soapenv:Envelope>"""

        headers = {'Content-Type': 'text/xml'}

        try:
            resp = requests.post(SOAP_URL_EDWARDS, headers=headers, data=payload)
            if resp.status_code != 200:
                print(f"[!] HTTP error for {product_id}: {resp.status_code}")
                return None

            xml_root = ET.fromstring(resp.text)

            # Namespaces for XML elements
            namespaces = {
                'ns2': 'http://www.promostandards.org/WSDL/ProductDataService/1.0.0/',
                'def': 'http://www.promostandards.org/WSDL/ProductDataService/1.0.0/SharedObjects/',
                'ns3': 'http://www.promostandards.org/WSDL/ProductDataService/1.0.0/SharedObjects/',

            }

            product = xml_root.find('.//ns2:Product', namespaces)
            if product is None:
                print(f"[!] No product found in response for {product_id}")
                return None

            def get_text(elem, tag):
                e = elem.find(tag, namespaces)
                return e.text.strip() if e is not None and e.text else None

            product_id_val = get_text(product, 'def:productId')
            product_name = get_text(product, 'ns2:productName')
            product_brand = get_text(product, 'ns2:productBrand')
            # image_url = get_text(product, 'def:primaryImageUrl')
            # Descriptions combined
            descriptions = [d.text.strip() for d in product.findall('ns3:description', namespaces) if d.text]
            combined_description = " ".join(descriptions)

            # Keywords
            keywords = []
            keyword_array = product.find('ns2:ProductKeywordArray', namespaces)
            if keyword_array is not None:
                for kw in keyword_array.findall('ns2:ProductKeyword/ns2:keyword', namespaces):
                    if kw.text:
                        keywords.append(kw.text.strip())

            # Categories and subcategories extraction
            categories = []
            product_categories = product.findall('ns2:ProductCategoryArray/ns2:ProductCategory', namespaces)
            for cat in product_categories:
                cat_name_el = cat.find('ns2:category', namespaces)
                sub_cat_el = cat.find('def:subCategory', namespaces)
                if cat_name_el is not None and cat_name_el.text:
                    categories.append(cat_name_el.text.strip())
                if sub_cat_el is not None and sub_cat_el.text:
                    # split comma separated subcategories and add individually
                    categories.extend([s.strip() for s in sub_cat_el.text.split(',')])

            # Product parts info
            colors = set()
            sizes = set()
            gtin = None
            flags = {}

            product_parts = product.findall('ns2:ProductPartArray/ns2:ProductPart', namespaces)
            for part in product_parts:
                primary_color = part.find('ns2:primaryColor/def:Color/def:standardColorName', namespaces)
                if primary_color is not None and primary_color.text:
                    colors.add(primary_color.text.strip())

                color_array = part.findall('ns2:ColorArray/ns2:Color/ns2:colorName', namespaces)
                for c in color_array:
                    if c.text:
                        colors.add(c.text.strip())

                apparel_size = part.find('def:ApparelSize', namespaces)
                if apparel_size is not None:
                    label_size = apparel_size.find('def:labelSize', namespaces)
                    if label_size is not None and label_size.text:
                        sizes.add(label_size.text.strip())

                gtin_el = part.find('def:gtin', namespaces)
                if gtin_el is not None and gtin_el.text:
                    gtin = gtin_el.text.strip()

                for flag_name in ['isRushService', 'isCloseout', 'isCaution', 'isOnDemand', 'isHazmat']:
                    flag_el = part.find(f'def:{flag_name}', namespaces)
                    if flag_el is not None and flag_el.text:
                        flags[flag_name] = flag_el.text.strip().lower() == 'true'

            product_data = {
                "product_id": product_id_val,
                "name": product_name,
                "brand": product_brand,
                # "image_url": image_url,
                "description": combined_description,
                "keywords": keywords,
                "categories": categories,
                "colors": list(colors),
                "sizes": list(sizes),
                "gtin": gtin,
                "flags": flags
            }
            return product_data

        except Exception as e:
            print(f"[!] Exception for {product_id}: {e}")
            return None
