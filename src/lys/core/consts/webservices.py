# Webservice Public Type Constants
# These define how webservices can be accessed by different user states

# Webservice accessible without any restrictions
NO_LIMITATION_WEBSERVICE_PUBLIC_TYPE = "NO_LIMITATION"

# Webservice only accessible to disconnected (anonymous) users
DISCONNECTED_WEBSERVICE_PUBLIC_TYPE = "DISCONNECTED"

# Access Level Constants
# These define the different types of access permissions in the system

# If the user is connected he can reach the data
CONNECTED_ACCESS_LEVEL = "CONNECTED"

# If the requested data belong to the user, he can reach it
OWNER_ACCESS_LEVEL = "OWNER"

# Access level for internal service-to-service communication
INTERNAL_SERVICE_ACCESS_LEVEL = "INTERNAL_SERVICE"