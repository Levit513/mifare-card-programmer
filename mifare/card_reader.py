"""
Card Reader Interface for MIFARE cards

Provides functionality to interact with PC/SC compatible card readers.
"""

from smartcard.System import readers
from smartcard.util import toHexString, toBytes
from smartcard.CardType import AnyCardType
from smartcard.CardRequest import CardRequest
from smartcard.Exceptions import CardRequestTimeoutException, NoCardException
import time

class CardReader:
    """Interface for reading MIFARE cards via PC/SC"""
    
    def __init__(self):
        self.connection = None
        self.card = None
    
    def list_readers(self):
        """List all available card readers"""
        try:
            reader_list = readers()
            return [str(reader) for reader in reader_list]
        except Exception as e:
            raise Exception(f"Failed to list readers: {e}")
    
    def scan_cards(self, timeout=5):
        """Scan for available cards"""
        cards_found = []
        
        try:
            reader_list = readers()
            if not reader_list:
                raise Exception("No card readers found")
            
            for reader in reader_list:
                try:
                    # Create card request
                    cardtype = AnyCardType()
                    cardrequest = CardRequest(timeout=timeout, cardType=cardtype, readers=[reader])
                    
                    # Wait for card
                    cardservice = cardrequest.waitforcard()
                    cardservice.connection.connect()
                    
                    # Get ATR (Answer To Reset)
                    atr = cardservice.connection.getATR()
                    atr_hex = toHexString(atr)
                    
                    cards_found.append({
                        'reader': str(reader),
                        'atr': atr_hex,
                        'connection': cardservice.connection
                    })
                    
                    cardservice.connection.disconnect()
                    
                except CardRequestTimeoutException:
                    # No card in this reader
                    continue
                except Exception as e:
                    print(f"Error with reader {reader}: {e}")
                    continue
            
            return cards_found
            
        except Exception as e:
            raise Exception(f"Card scan failed: {e}")
    
    def connect_to_card(self, reader_name=None):
        """Connect to a card in the specified reader"""
        try:
            reader_list = readers()
            if not reader_list:
                raise Exception("No card readers found")
            
            # Use first reader if none specified
            if reader_name is None:
                target_reader = reader_list[0]
            else:
                target_reader = None
                for reader in reader_list:
                    if reader_name in str(reader):
                        target_reader = reader
                        break
                
                if target_reader is None:
                    raise Exception(f"Reader '{reader_name}' not found")
            
            # Connect to card
            cardtype = AnyCardType()
            cardrequest = CardRequest(timeout=5, cardType=cardtype, readers=[target_reader])
            cardservice = cardrequest.waitforcard()
            
            self.connection = cardservice.connection
            self.connection.connect()
            
            return {
                'reader': str(target_reader),
                'atr': toHexString(self.connection.getATR())
            }
            
        except Exception as e:
            raise Exception(f"Failed to connect to card: {e}")
    
    def send_apdu(self, apdu_command):
        """Send APDU command to connected card"""
        if not self.connection:
            raise Exception("No card connected")
        
        try:
            if isinstance(apdu_command, str):
                # Convert hex string to bytes
                apdu_bytes = toBytes(apdu_command.replace(' ', ''))
            else:
                apdu_bytes = apdu_command
            
            response, sw1, sw2 = self.connection.transmit(apdu_bytes)
            
            return {
                'response': response,
                'sw1': sw1,
                'sw2': sw2,
                'status': f"{sw1:02X}{sw2:02X}"
            }
            
        except Exception as e:
            raise Exception(f"APDU transmission failed: {e}")
    
    def read_card(self, card_id=None):
        """Read basic information from MIFARE card"""
        try:
            # Connect to card
            card_info = self.connect_to_card()
            
            # Try to get card UID (for MIFARE cards)
            uid_response = self.send_apdu("FFCA000000")  # Get UID command
            
            card_data = {
                'reader': card_info['reader'],
                'atr': card_info['atr'],
                'uid': None,
                'type': 'Unknown'
            }
            
            if uid_response['sw1'] == 0x90 and uid_response['sw2'] == 0x00:
                card_data['uid'] = toHexString(uid_response['response'])
                card_data['type'] = self._identify_card_type(card_info['atr'])
            
            return card_data
            
        except Exception as e:
            raise Exception(f"Card read failed: {e}")
        finally:
            self.disconnect()
    
    def _identify_card_type(self, atr):
        """Identify MIFARE card type based on ATR"""
        atr_upper = atr.upper().replace(' ', '')
        
        # Common MIFARE ATR patterns
        if '3B8F8001804F0CA000000306030001000000006A' in atr_upper:
            return 'MIFARE Classic 1K'
        elif '3B8F8001804F0CA000000306030002000000006B' in atr_upper:
            return 'MIFARE Classic 4K'
        elif '3B8080018080' in atr_upper:
            return 'MIFARE Ultralight'
        elif '3B8A80018080' in atr_upper:
            return 'MIFARE DESFire'
        else:
            return f'MIFARE (ATR: {atr})'
    
    def disconnect(self):
        """Disconnect from card"""
        if self.connection:
            try:
                self.connection.disconnect()
            except:
                pass
            finally:
                self.connection = None
                self.card = None
