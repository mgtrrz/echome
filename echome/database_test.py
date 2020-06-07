from backend.user import User
from backend.id_gen import IdGenerator
from backend.database import DbEngine

# user.init_session()
# for user in session.query(user).filter_by(username='marknine'):
#     print(user)

# Initializing a SQLAlchemy session

#db = DbEngine()
#dbsession = db.return_session()
#print(dbsession)

# user = dbsession.query(User).filter_by(user_id="usr-90334826").first()
# print(user)

# user.init_session()
# user.add()



#################
# Creating a user
# user = User(
#     user_id=IdGenerator.generate("user"),
#     primary=True,
#     account="12345",
#     username="marknine",
#     name="Marcus"
# )

#################
# Working with an existing user
db = DbEngine()
dbsession = db.return_session()
# user = dbsession.query(User).filter_by(user_id="user-f6b15db4").first()
# print(user)


# Creating the table (and returning a session)
#session = user.init_session()

# Setting a password
#user.set_password("MyPassword")
#session.add(user)
#session.commit()

# Create API client and secret for this user
# user_api_obj, secret_token = user.create_api_auth()

# session.add(user_api_obj)
# session.commit()
# print(secret_token)

# Checking to see if the password or secret match
#print(user.check_password("MyPassword"))