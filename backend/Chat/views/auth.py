from django.contrib.auth import authenticate, get_user_model, login
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


def _user_payload(user):
    display_name = (user.get_full_name() or '').strip() or user.username
    token, _created = Token.objects.get_or_create(user=user)
    return {'id': user.id, 'username': user.username, 'name': display_name, 'token': token.key}


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        user = authenticate(username=request.data.get('username'), password=request.data.get('password'))
        if user is None:
            return Response({'error': 'Invalid credentials'}, status=401)
        login(request, user)
        return Response(_user_payload(user))


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        name = (request.data.get('name') or '').strip()
        if not username or not password:
            return Response({'error': 'Username and password are required'}, status=400)
        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=400)
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=400)
        user = User.objects.create_user(username=username, password=password, first_name=name)
        return Response(_user_payload(user), status=201)


class MeView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=204)