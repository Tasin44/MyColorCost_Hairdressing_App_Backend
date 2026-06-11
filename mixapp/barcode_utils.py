# import requests
# from django.conf import settings
# from typing import Optional, Dict, Any
# import logging

# logger = logging.getLogger(__name__)

# class BarcodeSpiderAPI:
#     """
#     Wrapper for Barcode Spider API
#     Handles product lookups and searches
#     """
    
#     def __init__(self):
#         self.api_key = settings.BARCODE_SPIDER_API_KEY
#         self.base_url = settings.BARCODE_SPIDER_BASE_URL
#         self.timeout = 10  # seconds
    
#     def lookup_barcode(self, upc: str) -> Optional[Dict[str, Any]]:
#         """
#         Lookup product by UPC/barcode
        
#         Args:
#             upc: Barcode/UPC string
            
#         Returns:
#             Product data dict if found, None otherwise
#         """
#         try:
#             # Build API URL
#             url = f"{self.base_url}/lookup"
#             params = {
#                 'token': self.api_key,
#                 'upc': upc
#             }
            
#             # Make API request
#             response = requests.get(url, params=params, timeout=self.timeout)
            
#             # Check response status
#             if response.status_code == 200:
#                 data = response.json()
                
#                 # Check if product found in API response
#                 if data.get('item_response') and data['item_response'].get('code') == 200:
#                     return self._parse_product_data(data['item_response'])
#                 else:
#                     logger.info(f"Product not found for UPC: {upc}")
#                     return None
#             else:
#                 logger.error(f"Barcode Spider API error: {response.status_code}")
#                 return None
                
#         except requests.exceptions.Timeout:
#             logger.error(f"Barcode Spider API timeout for UPC: {upc}")
#             return None
#         except requests.exceptions.RequestException as e:
#             logger.error(f"Barcode Spider API request error: {str(e)}")
#             return None
#         except Exception as e:
#             logger.error(f"Unexpected error in barcode lookup: {str(e)}")
#             return None
    
#     def search_product(self, query: str) -> Optional[list]:
#         """
#         Search products by name/keyword
        
#         Args:
#             query: Search query string
            
#         Returns:
#             List of product data dicts if found, None otherwise
#         """
#         try:
#             # Build API URL
#             url = f"{self.base_url}/search"
#             params = {
#                 'token': self.api_key,
#                 's': query
#             }
            
#             # Make API request
#             response = requests.get(url, params=params, timeout=self.timeout)
            
#             # Check response status
#             if response.status_code == 200:
#                 data = response.json()
                
#                 # Parse search results
#                 if data.get('item_list'):
#                     return [self._parse_product_data(item) for item in data['item_list']]
#                 else:
#                     logger.info(f"No products found for query: {query}")
#                     return []
#             else:
#                 logger.error(f"Barcode Spider API search error: {response.status_code}")
#                 return None
                
#         except requests.exceptions.Timeout:
#             logger.error(f"Barcode Spider API timeout for query: {query}")
#             return None
#         except requests.exceptions.RequestException as e:
#             logger.error(f"Barcode Spider API request error: {str(e)}")
#             return None
#         except Exception as e:
#             logger.error(f"Unexpected error in product search: {str(e)}")
#             return None
    
#     def _parse_product_data(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Parse Barcode Spider API response into our format
        
#         Args:
#             api_data: Raw API response data
            
#         Returns:
#             Standardized product data dict
#         """
#         # Extract product info from API response
#         # Adjust field names based on actual Barcode Spider response structure
#         return {
#             'name': api_data.get('title', api_data.get('name', 'Unknown Product')),
#             'description': api_data.get('description', ''),
#             'barcode': api_data.get('upc', ''),
#             'brand': api_data.get('brand', ''),
#             'image_url': self._get_first_image(api_data),
#             'category': api_data.get('category', ''),
#             # Note: Barcode Spider may not provide price, you'll need to set manually
#             'raw_data': api_data  # Store full response for debugging
#         }
    
#     def _get_first_image(self, api_data: Dict[str, Any]) -> Optional[str]:
#         """
#         Extract first image URL from API response
        
#         Args:
#             api_data: Raw API response data
            
#         Returns:
#             Image URL string or None
#         """
#         # Check various possible image fields
#         if api_data.get('images') and len(api_data['images']) > 0:
#             return api_data['images'][0]
#         elif api_data.get('image'):
#             return api_data['image']
#         return None


# # Create singleton instance
# barcode_api = BarcodeSpiderAPI()


#--------------------------------------------------------------
# import requests
# from decimal import Decimal

# class BarcodeSpiderAPI:
#     BASE_URL = "https://api.barcodespider.com/v1"
#     TOKEN = "c7942a6929183658052f"
    
#     def lookup_barcode(self, upc):
#         """Lookup product by barcode/UPC"""
#         try:
#             url = f"{self.BASE_URL}/lookup"
#             params = {
#                 'token': self.TOKEN,
#                 'upc': upc
#             }
            
#             response = requests.get(url, params=params, timeout=10)
            
#             if response.status_code == 200:
#                 data = response.json()
                
#                 # ✅ FIX 1: Check if product was found
#                 if data.get('item_response', {}).get('code') == 200:
#                     attrs = data.get('item_attributes', {})
                    
#                     # ✅ FIX 2: Validate item_attributes has actual data
#                     if not attrs or not attrs.get('title'):
#                         print(f"❌ Product not found in Barcode Spider for UPC: {upc}")
#                         return None  # ✅ Return None if no title
                    
#                     # ✅ FIX 3: Only return if we have valid product data
#                     return {
#                         'name': attrs.get('title'),  # ✅ No default fallback
#                         'description': attrs.get('description', ''),
#                         'brand': attrs.get('brand', ''),
#                         'image_url': attrs.get('image', ''),
#                         'weight': attrs.get('weight', ''),
#                         'category': attrs.get('category', ''),
#                         'upc': attrs.get('upc', upc)
#                     }
#                 else:
#                     # ✅ FIX 4: API explicitly says not found
#                     print(f"❌ API returned code: {data.get('item_response', {}).get('code')}")
#                     return None
#             else:
#                 print(f"❌ API request failed: {response.status_code}")
#                 return None
            
#         except Exception as e:
#             print(f"❌ Barcode API Error: {e}")
#             return None

# # Global instance
# barcode_api = BarcodeSpiderAPI()




#----------------------------------------------------------
# import requests
# from decimal import Decimal
# import logging

# logger = logging.getLogger(__name__)

# class BarcodeSpiderAPI:
#     """
#     Barcode Spider API wrapper
#     Only returns product data if ACTUALLY found, otherwise returns None
#     """
    
#     BASE_URL = "https://api.barcodespider.com/v1"
#     TOKEN = "c7942a6929183658052f"
    
#     def lookup_barcode(self, upc):
#         """
#         Lookup product by UPC/barcode
        
#         Returns:
#             Dict with product data if found
#             None if not found or error
#         """
#         try:
#             url = f"{self.BASE_URL}/lookup"
#             params = {
#                 'token': self.TOKEN,
#                 'upc': upc
#             }
            
#             logger.info(f"🔍 Calling Barcode Spider API for UPC: {upc}")
            
#             response = requests.get(url, params=params, timeout=10)
            
#             if response.status_code != 200:
#                 logger.error(f"❌ API HTTP Error: {response.status_code}")
#                 return None
            
#             data = response.json()
#             logger.info(f"📥 API Response: {data}")
            
#             # ✅ FIX 1: Check if API returned success
#             item_response = data.get('item_response', {})
#             if item_response.get('code') != 200:
#                 logger.info(f"❌ API says product not found (code: {item_response.get('code')})")
#                 return None
            
#             # ✅ FIX 2: Get item_attributes
#             item_attributes = data.get('item_attributes', {})
            
#             # ✅ FIX 3: Validate item_attributes has REAL data
#             if not item_attributes:
#                 logger.info(f"❌ item_attributes is empty")
#                 return None
            
#             # ✅ FIX 4: Check if 'title' exists and is not empty
#             title = item_attributes.get('title', '').strip()
#             if not title:
#                 logger.info(f"❌ Product title is empty")
#                 return None
            
#             # ✅ FIX 5: Only return if we have valid product data
#             product_data = {
#                 'name': title,  # ✅ Already validated above
#                 'description': item_attributes.get('description', ''),
#                 'brand': item_attributes.get('brand', ''),
#                 'image_url': item_attributes.get('image', ''),
#                 'weight': item_attributes.get('weight', ''),
#                 'category': item_attributes.get('category', ''),
#                 'upc': item_attributes.get('upc', upc),
#                 'raw_data': item_attributes  # Store for debugging
#             }
            
#             logger.info(f"✅ Product found: {product_data['name']}")
#             return product_data
            
#         except requests.exceptions.Timeout:
#             logger.error(f"⏱️ API Timeout for UPC: {upc}")
#             return None
#         except requests.exceptions.RequestException as e:
#             logger.error(f"🌐 API Request Error: {str(e)}")
#             return None
#         except Exception as e:
#             logger.error(f"💥 Unexpected Error: {str(e)}", exc_info=True)
#             return None
    
#     def search_product(self, query):
#         """
#         Search products by name/keyword
        
#         Returns:
#             List of product dicts if found
#             Empty list if not found
#             None on error
#         """
#         try:
#             url = f"{self.BASE_URL}/search"
#             params = {
#                 'token': self.TOKEN,
#                 's': query
#             }
            
#             logger.info(f"🔍 Searching for: {query}")
            
#             response = requests.get(url, params=params, timeout=10)
            
#             if response.status_code != 200:
#                 logger.error(f"❌ Search API Error: {response.status_code}")
#                 return None
            
#             data = response.json()
#             item_list = data.get('item_list', [])
            
#             if not item_list:
#                 logger.info(f"❌ No search results for: {query}")
#                 return []
            
#             # Parse each result
#             results = []
#             for item in item_list:
#                 title = item.get('title', '').strip()
#                 if title:  # Only include items with valid title
#                     results.append({
#                         'name': title,
#                         'description': item.get('description', ''),
#                         'brand': item.get('brand', ''),
#                         'image_url': item.get('image', ''),
#                         'upc': item.get('upc', ''),
#                         'category': item.get('category', '')
#                     })
            
#             logger.info(f"✅ Found {len(results)} products")
#             return results
            
#         except Exception as e:
#             logger.error(f"💥 Search Error: {str(e)}", exc_info=True)
#             return None


# # ✅ Create singleton instance
# barcode_api = BarcodeSpiderAPI()

#----------------------------------------------------------------
'''
import requests
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class BarcodeSpiderAPI:
    """
    Barcode Spider API wrapper
    Sends token as HEADER (not query param) per their documentation
    """
    
    BASE_URL = "https://api.barcodespider.com/v2"
    TOKEN = "2dfeae0078c7257f3f4c0ecfe71290f3"
    
    def lookup_barcode(self, upc):
        """Lookup product by UPC/barcode"""
        try:
            url = f"{self.BASE_URL}/lookup"
            
            headers = {
                'token': self.TOKEN,
                'Host': 'api.barcodespider.com',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'cache-control': 'no-cache'
            }
            
            params = {'upc': upc}
            
            # ✅ CRITICAL: Log everything BEFORE making request
            print(f"🔍 REQUEST URL: {url}?upc={upc}")
            print(f"🔍 HEADERS: {headers}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # ✅ CRITICAL: Log raw response BEFORE parsing
            print(f"📥 STATUS CODE: {response.status_code}")
            print(f"📥 RAW RESPONSE: {response.text}")
            print(f"📥 RESPONSE HEADERS: {dict(response.headers)}")
            
            # ✅ Check status code
            if response.status_code != 200:
                print(f"❌ HTTP ERROR: {response.status_code}")
                return None
            
            data = response.json()
            print(f"📦 PARSED JSON: {data}")
            
            # Check API response
            item_response = data.get('item_response', {})
            if item_response.get('code') != 200:
                print(f"❌ API SAYS NOT FOUND: {item_response}")
                return None
            
            item_attributes = data.get('item_attributes', {})
            if not item_attributes or not item_attributes.get('title'):
                print(f"❌ NO TITLE IN RESPONSE")
                return None
            
            print(f"✅ PRODUCT FOUND: {item_attributes.get('title')}")
            
            return {
                'name': item_attributes.get('title'),
                'description': item_attributes.get('description', ''),
                'brand': item_attributes.get('brand', ''),
                'manufacturer': item_attributes.get('manufacturer', ''),
                'image_url': item_attributes.get('image', ''),
                'weight': item_attributes.get('weight', ''),
                'category': item_attributes.get('category', ''),
                'model': item_attributes.get('model', ''),
                'asin': item_attributes.get('asin', ''),
                'mpn': item_attributes.get('mpn', ''),
                'upc': item_attributes.get('upc', upc),
                'ean': item_attributes.get('ean', ''),
                'color': item_attributes.get('color', ''),
                'size': item_attributes.get('size', ''),
                'raw_data': data  # ✅ ENTIRE API RESPONSE INCLUDING STORES
            }
            
        except requests.exceptions.RequestException as e:
            print(f"💥 NETWORK ERROR: {str(e)}")
            raise  # ✅ DON'T CATCH - LET IT FAIL LOUDLY
        except Exception as e:
            print(f"💥 UNEXPECTED ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            raise  # ✅ DON'T CATCH - LET IT FAIL LOUDLY
    def search_product(self, query):
        """
        Search products by name/keyword
        
        Args:
            query: Search query string
            
        Returns:
            List of product dicts if found, empty list if not found, None on error
        """
        try:
            url = f"{self.BASE_URL}/search"
            
            # ✅ Send token as header
            headers = {
                'token': self.TOKEN,
                'Host': 'api.barcodespider.com',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'cache-control': 'no-cache'
            }
            
            # ✅ Only search query in params
            params = {
                's': query
            }
            
            logger.info(f"🔍 Searching for: {query}")
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ Search API Error: {response.status_code}")
                return None
            
            data = response.json()
            item_list = data.get('item_list', [])
            
            if not item_list:
                logger.info(f"❌ No search results for: {query}")
                return []
            
            # Parse each result
            results = []
            for item in item_list:
                title = item.get('title', '').strip()
                if title:  # Only include items with valid title
                    results.append({
                        'name': title,
                        'description': item.get('description', ''),
                        'brand': item.get('brand', ''),
                        'image_url': item.get('image', ''),
                        'upc': item.get('upc', ''),
                        'category': item.get('category', '')
                    })
            
            logger.info(f"✅ Found {len(results)} products")
            return results
            
        except Exception as e:
            logger.error(f"💥 Search Error: {str(e)}", exc_info=True)
            return None


# ✅ Create singleton instance
barcode_api = BarcodeSpiderAPI()
'''
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class BarcodeSpiderAPI:
    """Barcode Spider API v2 wrapper - uses key query param per official docs"""
    
    BASE_URL = os.getenv('BARCODE_SPIDER_BASE_URL', 'https://api.barcodespider.com/v2/')
    API_KEY = os.getenv('BARCODE_SPIDER_API_KEY')
    
    def lookup_barcode(self, upc):
        """Lookup product by UPC/barcode using v2 endpoint"""
        try:
            # ✅ CORRECT: v2 uses /products/{upc} with key as query param
            url = f"{self.BASE_URL.rstrip('/')}/products/{upc}"
            
            params = {'key': self.API_KEY}
            
            print(f"🔍 REQUEST URL: {url}?key={self.API_KEY}")
            
            response = requests.get(url, params=params, timeout=10)
            
            print(f"📥 STATUS CODE: {response.status_code}")
            print(f" RAW RESPONSE: {response.text}")
            
            if response.status_code != 200:
                print(f"❌ HTTP ERROR: {response.status_code}")
                return None
            
            data = response.json()
            
            # Check for different possible structures in Barcode Spider response
            # 1. Nesting under 'product' (standard v2 format seen in response logs)
            # 2. Nesting under 'item_attributes' (older format)
            # 3. Flat format (fallback)
            if 'product' in data:
                item = data['product']
                title = item.get('name')
                description = item.get('description', '')
                brand = item.get('brand', '')
                manufacturer = item.get('manufacturer', '')
                
                # Extract image url from images list if available
                images = item.get('images', [])
                image_url = images[0] if (isinstance(images, list) and len(images) > 0) else item.get('image', '')
                
                weight = item.get('weight', '')
                
                # Category can be a dict or a string
                category_data = item.get('category', '')
                if isinstance(category_data, dict):
                    category = category_data.get('path', '')
                else:
                    category = category_data
                    
                model = item.get('model', '')
                asin = item.get('asin', '')
                mpn = item.get('mpn', '')
                
                # UPC/EAN from identifiers values
                identifiers = data.get('identifiers', {})
                values = identifiers.get('values', {})
                upc_val = values.get('upc') or item.get('upc') or upc
                ean_val = values.get('ean13') or item.get('ean') or ''
                color = item.get('color', '')
                size = item.get('size', '')
            else:
                item = data.get('item_attributes', data)
                title = item.get('title')
                description = item.get('description', '')
                brand = item.get('brand', '')
                manufacturer = item.get('manufacturer', '')
                image_url = item.get('image', '')
                weight = item.get('weight', '')
                category = item.get('category', '')
                model = item.get('model', '')
                asin = item.get('asin', '')
                mpn = item.get('mpn', '')
                upc_val = item.get('upc', upc)
                ean_val = item.get('ean', '')
                color = item.get('color', '')
                size = item.get('size', '')
            
            if not title:
                print("❌ NO TITLE IN RESPONSE")
                return None
            
            print(f"✅ PRODUCT FOUND: {title}")
            
            return {
                'name': title,
                'description': description,
                'brand': brand,
                'manufacturer': manufacturer,
                'image_url': image_url,
                'weight': weight,
                'category': category,
                'model': model,
                'asin': asin,
                'mpn': mpn,
                'upc': upc_val,
                'ean': ean_val,
                'color': color,
                'size': size,
                'raw_data': data
            }
            
        except Exception as e:
            print(f"💥 ERROR: {str(e)}")
            raise
    
    def search_product(self, query):
        """Search products by keyword using v2 endpoint"""
        try:
            # ✅ CORRECT: v2 uses /products?query=...
            url = f"{self.BASE_URL.rstrip('/')}/products"
            
            params = {
                'key': self.API_KEY,
                'query': query
            }
            
            print(f"🔍 SEARCH URL: {url}?query={query}&key=***")
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Search API Error: {response.status_code}")
                return []
            
            data = response.json()
            item_list = data.get('item_list', [])
            
            if not item_list:
                print(f" No results for: {query}")
                return []
            
            results = []
            for item in item_list:
                title = item.get('title', '').strip()
                if title:
                    results.append({
                        'name': title,
                        'description': item.get('description', ''),
                        'brand': item.get('brand', ''),
                        'image_url': item.get('image', ''),
                        'upc': item.get('upc', ''),
                        'category': item.get('category', '')
                    })
            
            print(f"✅ Found {len(results)} products")
            return results
            
        except Exception as e:
            print(f"💥 Search Error: {str(e)}")
            return []


# Singleton instance
barcode_api = BarcodeSpiderAPI()