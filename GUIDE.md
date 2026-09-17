<!-- backend -->

cd apps/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m src.main

<!-- frontend -->

cd apps/web
npm i
npm run dev