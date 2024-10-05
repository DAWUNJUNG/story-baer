import os
import json
import urllib.request
from dotenv import load_dotenv
from flask import Flask, render_template, redirect, url_for, request, flash
from google_auth_oauthlib.flow import InstalledAppFlow
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from img2pdf import convert

# dotenv
load_dotenv(verbose=True)

# Flask
app = Flask(__name__)

# Google OAuth
client_config = {
    "installed": {
        "client_id": os.getenv('CLIENT_ID'),
        "client_secret": os.getenv('CLIENT_SECRET'),
        "redirect_uri": 'urn:ietf:wg:oauth:2.0:oob',
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "grant_type": "authorization_code"
    }
}
SCOPES = ['openid',
          'https://www.googleapis.com/auth/userinfo.email',
          'https://www.googleapis.com/auth/userinfo.profile']

# Open AI
client = OpenAI()


@app.route('/', methods=['GET'])
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET'])
def login():
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = "http://127.0.0.1:5000/google-auth/callback"

    auth_url, _ = flow.authorization_url(prompt='consent')

    return render_template('login.html', googleAuthUrl=auth_url)


@app.route('/google-auth/callback', methods=['GET'])
def googleAuthCallback():
    return redirect(url_for('list'))


@app.route('/list', methods=['GET'])
def list():
    bookList = []
    for dirName in os.listdir('static/storage'):
        bookList.append({
                "name": dirName,
                "path": f"storage/{dirName}",
                "thumbnail": f"storage/{dirName}/cover.png",
                "ebook": f"storage/{dirName}/ebook.pdf",
            })

    return render_template('main.html', bookList=bookList)


@app.route('/new-book', methods=['GET'])
def newBook():
    return render_template('newBook.html')


@app.route('/test', methods=['GET'])
def test():
    return render_template('imagePage.html')


@app.route('/make', methods=['POST'])
def makeBook():
    # parameter
    setTitle = request.form.get('setTitle')
    ignoreTitle = request.form.get('ignoreTitle')

    # 프롬프트 제작
    gptPrompt = """동화를 시나리오를 작성해줘. 동화 이야기 주제는 아이들이 흥미를 느낄 수 있는 내용이며, 너무 자극적이지 않은 내용으로 관심을 끌 수 있는 주제여야 해.
하나의 주제로 이야기는 10개 이상을 만들어야 하고, 주제에 맞게 이야기가 처음부터 자연스럽게 이어가야해.
총 10개의 이야기에는 각각 장면을 나타내는 그림이 만들 수 있도록 60자 이내로 상세하게 장면을 설명해줘야해.
장면 마다 등장인물이 존재해야 하고, 등장인물은 사람이여도 되고, 동물이여도 돼.
아이들이 볼 수 있도록 자극적이거나 성적인 내용으로 작성되면 안되고, 아이들의 관심사을 높히기 위한 내용으로 동화 주제가 정해지고 이야기가 작성되면 좋겠어.
장면에는 주변에 집, 길, 자연 등 다양한 사물로 지정해도 되고, 장면은 부드럽고 귀여운 느낌으로 표현되어야해.
위 내용을 아래 json 포맷 형태로 결과를 출력해줘.
출력시에는 {제목}에는 주제에 대한 알맞은 제목을 작성해주고, {요약}에는 동화 이야기 전체 내용을 요약하여 그림으로 표현할 수 있게 상세하게 작성해주고 내용은 40자 이내로 작성해줘.
그리고 이야기는 pages 안에 작성해줘. 이야기마다 장면 그림 설명은 {장면 상세 설명}에 60자 이내로 상세하게 작성해주고, 이야기마다 나오는 등장인물은 character에 {"캐릭터 이름":"성별"} 형태로 작성해줘.
각 이야기 마다 {장면 설명 및 대사}에 장면에 대한 간략한 설명과 해당 장면에서 등장인물들의 대화를 스토리 형식으로 작성해줘.
장면에 대한 설명을 작성하고 줄바꿈을 한 뒤에 등장인물 별 대사를 작성해줘. 대사를 작성할 때는 대사 맨 앞에 누가 말한 것인지 등장인물의 이름을 작성해줘. 대사는 줄바꿈으로 구분해줘.
{장면 설명 및 대사}는 작성할 때 장면 설명은 60자 이상 작성해주고, 인물당 대사는 최소 20자 이상 작성해줘. 단 글을 작성할 때 한줄에 10자까지만 작성해주고, 만약 글이 10자가 넘으면 줄바꿈해서 자연스럽게 이어서 작성해줘."""
    gptFormat = """[json 포맷]
{
    "title": "{제목}",
    "summary": "{요약}",
    "pages": [
        {
            "seenSummary": "{장면 상세 설명}",
            "description": "{장면 설명 및 대사}"
            "character": {
                "{캐릭터 이름1}": "{캐릭터 성별}"
            }
        }
    ]
}"""
    coverPrompt = """장면에 대한 설명을 기준으로 그려주고, 동화 속에 나오는 그림체로 그려줘. 그림은 반드시 세로로 그려져야해"""
    seenPrompt = """아래 장면에 대한 설명을 기준으로 그려줘. 장면에 대한 설명을 이해하고 상황을 그림으로 표현해줘. 그림은 반드시 세로로 그려져야해"""

    # 프롬프트 제외 사항이 있으면 추가
    if setTitle is not None:
        gptPrompt += f" 해당 내용에 주제는 반드시 {setTitle}로 해줘."
    if ignoreTitle is not None:
        gptPrompt += f" 동화에서 {ignoreTitle}로 주제 및 이야기를 만들면 안돼."

    # 시나리오 제작
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "너는 동화를 만드는 동화 작가야. 아이들이 좋아할만한 주제로 이야기를 쓰고, 그 이야기에 맞게 장면을 어떻게 그림으로 표현해야 하는지 작성할 수 있는 작가야"
            },
            {
                "role": "user",
                "content": f'{gptPrompt}{gptFormat}'
            }
        ],
        response_format={"type": "json_object"}
    )

    story = json.loads(completion.choices[0].message.content)

    title = story['title']
    summary = story['summary']
    pages = story['pages']

    # 파일 저장 경로 생성
    if not os.path.isdir(f'static/storage/{title}'):
        os.mkdir(f'static/storage/{title}')

    # 시나리오 파일 저장
    with open(f'static/storage/{title}/story.json', "w") as storyFile:
        storyFile.write(json.dumps(story))
        storyFile.close()

    # 표지 만들기
    coverResult = client.images.generate(
        model="dall-e-3",
        prompt=f'{coverPrompt}[장면설명]{summary}',
        size="1024x1792",
        quality="hd",
        n=1,
    )
    # 표지 다운로드
    urllib.request.urlretrieve(coverResult.data[0].url, f'static/storage/{title}/cover.png')

    pageList = []
    pageList.append(f'static/storage/{title}/cover.png')
    idx = 1
    for seen in pages:
        # 장면 별 그림 설명
        seenDescription = f"""{seen["seenSummary"]}를 나타내는 그림을 그려줘."""

        # 등장 인물 정보 정리
        charList = seen['character'].keys()
        seenDescription += f" 등장인물은 총 {len(charList)}명이고, "
        for charName in charList:
            seenDescription += f" {charName}의 성별은 {seen['character'][charName]}이며,"

        seenDescription += '모든 등장인물은 반드시 그림에 나오지 않아도 되고, 다양한 위치에 있을 수 있어.'

        # 장면 그림 만들기
        try:
            seenImgResult = client.images.generate(
                model="dall-e-3",
                prompt=f'{seenPrompt}[장면설명]{seenDescription}',
                size="1024x1792",
                quality="hd",
                n=1,
            )

            # 장면 그림 다운로드
            urllib.request.urlretrieve(seenImgResult.data[0].url, f'static/storage/{title}/{idx}.png')
        except:
            seenImgResult = client.images.generate(
                model="dall-e-3",
                prompt=f'{seenPrompt}[장면설명]{seenDescription}',
                size="1024x1792",
                quality="hd",
                n=1,
            )

            # 장면 그림 다운로드
            urllib.request.urlretrieve(seenImgResult.data[0].url, f'static/storage/{title}/{idx}.png')

        # 글자 이미지 생성
        width, height = 1024, 1792
        backgroundColor = (255, 255, 255)
        textColor = (0, 0, 0)

        image = Image.new('RGB', (width, height), backgroundColor)
        draw = ImageDraw.Draw(image)

        font_size = 40
        font = ImageFont.truetype('static/font/bookfont.otf', font_size)

        text = seen['description']
        _, _, text_width, text_height = draw.textbbox((0, 0), text, font)
        x = (width - text_width) // 2
        y = (height - text_height) // 2

        draw.text((x, y), text, font=font, fill=textColor)

        image.save(f'static/storage/{title}/{idx}-2.png')

        pageList.append(f'static/storage/{title}/{idx}.png')
        pageList.append(f'static/storage/{title}/{idx}-2.png')

        idx += 1

    # pdf 제작
    with open(f"static/storage/{title}/ebook.pdf", "wb") as f:
        pdf = convert(pageList)
        f.write(pdf)
        f.close()

    # alert 문구
    flash('동화 제작이 완료 되었습니다.')
    return render_template('alert.html', redirectUrl="/list")


if __name__ == '__main__':
    app.run()
