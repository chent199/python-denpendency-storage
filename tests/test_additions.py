"""Offline functional checks; database server connections require separate validation."""
import io


def test_numpy_pandas(tmp_path):
    import numpy as np
    import pandas as pd
    frame = pd.DataFrame({'value': np.array([1, 2, 3])})
    csv = tmp_path / 'data.csv'
    frame.to_csv(csv, index=False)
    loaded = pd.read_csv(csv)
    assert loaded['value'].sum() == 6
    assert np.linalg.solve(np.array([[2., 0.], [0., 4.]]), np.array([4., 8.])).tolist() == [2., 2.]
    xlsx = tmp_path / 'data.xlsx'
    frame.to_excel(xlsx, index=False, engine='openpyxl')
    assert pd.read_excel(xlsx, engine='openpyxl')['value'].tolist() == [1, 2, 3]


def test_pdf_roundtrip():
    from pypdf import PdfReader, PdfWriter
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=300)
    writer.add_metadata({'/Title': 'offline-pdf'})
    writer.write(stream)
    stream.seek(0)
    reader = PdfReader(stream)
    assert len(reader.pages) == 1
    assert reader.metadata.title == 'offline-pdf'


def test_pillow_png():
    from PIL import Image
    stream = io.BytesIO()
    Image.new('RGB', (3, 2), 'red').save(stream, format='PNG')
    stream.seek(0)
    with Image.open(stream) as image:
        assert image.getpixel((1, 1)) == (255, 0, 0)
        assert image.rotate(90, expand=True).size == (2, 3)


def test_html_css_selection():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup('<main><p class="item">offline</p></main>', 'html.parser')
    assert soup.select_one('main .item').get_text() == 'offline'


def test_settings_dotenv(tmp_path):
    from pydantic_settings import BaseSettings, SettingsConfigDict
    class Settings(BaseSettings):
        model_config = SettingsConfigDict(env_prefix='OFFLINE_STORAGE_TEST_')
        port: int
    env = tmp_path / '.env'
    env.write_text('OFFLINE_STORAGE_TEST_PORT=8123\n')
    assert Settings(_env_file=env).port == 8123


def test_excluded_database_packages_not_installed():
    import importlib.util
    for name in ('sqlalchemy', 'pymysql', 'oracledb', 'psycopg', 'psycopg2', 'mysql'):
        assert importlib.util.find_spec(name) is None
