import os
import chromadb
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF
import re
import json

# Define paths and model names (must match app.py for consistency)
CHROMA_DB_PATH = "./chroma_db_data"
EMBEDDER_MODEL_NAME = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2' # The 768-dim model

# --- Global Initialization for Ingestion ---
ingestion_chroma_client = None
ingestion_embedder = None

try:
    print(f"Initializing ChromaDB client for ingestion at: {CHROMA_DB_PATH}")
    ingestion_chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    print("ChromaDB client initialized for ingestion.")
except Exception as e:
    print(f"Error initializing ChromaDB client for ingestion: {e}")
    ingestion_chroma_client = None

try:
    print(f"Loading SentenceTransformer model for ingestion: {EMBEDDER_MODEL_NAME}")
    ingestion_embedder = SentenceTransformer(EMBEDDER_MODEL_NAME)
    print("SentenceTransformer model loaded for ingestion.")
except Exception as e:
    print(f"Error loading SentenceTransformer for ingestion: {e}")
    ingestion_embedder = None

# --- Helper Functions for Text Processing ---

def remove_common_headers(text: str) -> str:
    """
    Removes common header/footer patterns (e.g., page numbers, repetitive lines).
    This is a basic example; might need customization for your specific documents.
    """
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # Remove lines that are just numbers or very short strings (potential page numbers)
        if re.fullmatch(r'^\s*\d+\s*$', line) or len(line.strip()) < 5:
            continue
        filtered_lines.append(line)
    return '\n'.join(filtered_lines)

def clean_text_and_normalize_whitespace(text: str) -> str:
    """
    Cleans text: removes various symbols, collapses spaces, and handles newlines.
    """
    # Preserve '.\n' and '።\n' by temporarily replacing them, then clean, then restore
    text = text.replace('.\n', '[DOT_NEWLINE_ENG]')
    text = text.replace('።\n', '[DOT_NEWLINE_AMH]')

    # Remove various special characters and symbols
    text = re.sub(r'[\[\]{}<>“”"\'()_/\\=+@#%*~`|^•●]+', ' ', text)
    
    # Normalize all whitespace (tabs, newlines, multiple spaces) to single spaces
    text = re.sub(r'\s+', ' ', text)

    # Restore the preserved newlines (if any)
    text = text.replace('[DOT_NEWLINE_ENG]', '.\n')
    text = text.replace('[DOT_NEWLINE_AMH]', '።\n')

    # Remove standalone Amharic letters (single glyphs that might be noise)
    tokens = text.split()
    filtered_tokens = [
        word for word in tokens
        if not (len(word) == 1 and re.fullmatch(r'[\u1200-\u137F]', word))
    ]
    text = ' '.join(filtered_tokens)

    return text.strip()

def extract_amharic_text_only(text: str) -> str:
    """
    Extracts only Amharic script, numbers, and core punctuation from text.
    This is for filtering *after* initial cleaning if you only want Amharic.
    """
    amharic_pattern = re.compile(r'[\u1200-\u137F0-9\s\.\,\:\;\-\–\(\)\[\]\{\}\'\"!@#\$%\^&\*\+=\?\/\\]+')
    matches = amharic_pattern.findall(text)
    result_text = ''.join(matches).strip()
    return result_text

def split_into_sentences_amharic(text: str) -> list[str]:
    """
    Splits Amharic text into sentences using a more robust regex pattern
    to handle various sentence terminators common in Amharic texts,
    including the Ethiopic full stop, English period, question mark, and exclamation mark.
    """
    # Regex to split on '.', '?', '!', or '።' followed by whitespace or end of string.
    # It keeps the delimiter with the sentence.
    sentences = re.split(r'(?<=[\.\?\!።])\s+', text)
    
    # Filter out empty strings that might result from the split
    sentences = [s.strip() for s in sentences if s.strip()]
    return sentences
sentences= "እኛ የኢትዮጵያ ብሔሮች፣ ብሔረሰቦች፣ ሕዝቦች፡በሀገራችን ኢትዮጵያ ውስጥ ዘላቂ ሰላም፣ ዋስትና ያለው ዴሞክራሲ እንዲሰፍን፣ኢኮኖሚያዊና ማኅበራዊ እድገታችን እንዲፋጠን፣ የራሳችንን ዕድል በራሳችን የመወሰን መብታችንን ተጠቅመን፣ በነጻ ፍላጐታችን፣ በሕግ የበላይነት እና በራሳችን ፈቃድ ላይ የተመሰረተ አንድ የፖለቲካ ማኅበረሰብ በጋራ ለመገንባት ቆርጠን በመነሳት፤ይህን ዓላማ ከግብ ለማድረስ፣ የግለሰብና የብሔር ብሔረሰብ መሰረታዊ መብቶች መከበራቸው፣ የጾታ እኩልነት መረጋገጡ፣ ባሕሎችና ሃይማኖቶች ካለአንዳች ልዩነት እንዲራመዱ የማድረጉ አስፈላጊነት ጽኑ እምነታችን በመሆኑ፤ኢትዮጵያ ሀገራችን የየራሳችን አኩሪ ባሕል ያለን፣ የየራሳችን መልክዓ ምድር አሰፋፈር የነበረንና ያለን፣ ብሔር ብሔረሰቦችና ሕዝቦች በተለያዩ መስኮችና የግንኙነት ደረጃዎችተሳስረንአብረን የኖርንባትና የምንኖርባት ሀገር በመሆንዋ፤ ያፈራነው የጋራ ጥቅምና አመለካከት አለን ብለን ስለምናምን፤መጪው የጋራ ዕድላችን መመስረት ያለበት ከታሪካችን የወረስነውን የተዛባ ግንኙነት በማረምና የጋራ ጥቅማችንን በማሳደግ ላይ መሆኑን በመቀበል፤ ጥቅማችንን፣ መብታችንና ነጻነታችንን በጋራ እና በተደጋጋፊነት ለማሳደግ አንድ የኢኮኖሚ ማኅበረሰብ የመገንባቱን አስፈላጊነት በማመን፤ በትግላችንና በከፈልነው መስዋዕትነት የተገኘውን ዴሞክራሲና ሰላም ዘላቂነቱንለማረጋገጥ፤ይህ ሕገ መንግሥት ከዚህ በላይ ለገለጽናቸው ዓላማዎችና እምነቶች ማሰሪያ እንዲሆነንእንዲወክሉን መርጠን በላክናቸው ተወካዮቻቸን አማካይነት በሕገ መንግሥት ጉባኤ ዛሬ ኅዳር 29 ቀን 1987 አጽድቀነዋል፡፡ ምዕራፍ አንድ : ጠቅላላ ድንጋጌዎች አንቀጽ 1: የኢትዮጵያ መንግሥት ስያሜ ይህ ሕገ መንግሥት ፌዴራላዊና ዴሞክራሲያዊ የመንግሥት አወቃቀር ይደነግጋል፡፡በዚህ መሰረት የኢትዮጵያ መንግሥት የኢትዮጵያ ፌዴራላዊ ዴሞክራሲያዊ ሪፐብሊክ በሚል ስም ይጠራል፡፡ አንቀጽ 2: የኢትዮጵያ የግዛት ወሰን የኢትዮጵያ የግዛት ወሰን የፌዴራሉን አባሎች ወሰን የሚያጠቃልል ሆኖ በዓለም አቀፍ ስምምነቶች መሰረት የተወሰነው ነው፡፡ አንቀጽ 3:የኢትዮጵያ ሰንደቅ ዓላማ 1. የኢትዮጵያ ሰንደቅ ዓላማ ከላይ አረንጓዴ፣ ከመሐል ቢጫ፣ ከታች ቀይ ሆኖበመሐሉ ብሔራዊ ዓርማ ይኖረዋል፡፡ ሦስቱም ቀለማት እኩል ሆነው በአግድም ይቀመጣሉ፡፡ 2. ከሰንደቅ ዓላማው ላይ የሚቀመጠው ብሔራዊ ዓርማ የኢትዮጵያ ብሔሮች፣ብሔረሰቦች፣ ሕዝቦች እና ሃይማኖቶች በእኩልነትና በአንድነት ለመኖር ያላቸውን ተስፋ የሚያንጸባርቅ ይሆናል፡፡ 3. የፌዴራሉ አባሎች የየራሳቸው ሰንደቅ ዓላማና ዓርማ ሊኖራቸው ይችላል፡፡ ዝርዝሩን በየራሳቸው ምክር ቤት ይወስናሉ፡፡ አንቀጽ 4:የኢትዮጵያ ብሔራዊ መዝሙር የኢትዮጵያ ብሔራዊ መዝሙር የሕገ መንግሥቱን ዓላማዎችና የኢትዮጵያ ሕዝቦች በዴሞክራሲ ሥርዓት አብረው ለመኖር ያላቸውን እምነት፣ እንዲሁም የወደፊት የጋራ ዕድላቸውን የሚያንጸባርቅ ሆኖ በሕግ ይወሰናል፡፡ አንቀጽ 5:ስለ ቋንቋ 1. ማናቸውም የኢትዮጵያ ቋንቋዎች በእኩልነት የመንግሥት እውቅና ይኖራቸዋል፡፡ 2. አማርኛ የፌዴራሉ መንግሥት የሥራ ቋንቋ ይሆናል፡፡ 3. የፌዴሬሽኑ አባሎች የየራሳቸውን የሥራ ቋንቋ በሕግ ይወስናሉ፡፡ አንቀጽ 6: ስለ ዜግነት 1. ወላጆቹ ወላጆኟ ወይም ከወላጆቹ ከወላጆኟ አንደኛቸው ኢትዮጵያዊ ኢትዮጵያዊት የሆነ የሆነች የኢትዮጵያ ዜጋ ነው ናት፡፡ 2. የውጭ ሀገር ዜጐች የኢትዮጵያ ዜግነት ሊያገኙ ይችላሉ፡፡ 3. ዜግነትን በሚመለከት ዝርዝሩ በሕግ ይወሰናል፡፡ አንቀጽ 7: የፆታ አገላለጽ በዚህ ሕገ መንግሥት ውስጥ በወንድ ፆታ የተደነገገው የሴትንም ፆታ ያካትታል፡፡ ምዕራፍ ሁለት: የሕገ መንግሥቱ መሰረታዊ መርሆዎች አንቀጽ 8: የሕዝብ ሉዓላዊነት 1. የኢትዮጵያ ብሔሮች፣ ብሔረሰቦች፣ ሕዝቦች የኢትዮጵያ ሉዓላዊ ሥልጣንባለቤቶች ናቸው፡፡ 2. ይህ ሕገ መንግሥት የሉዓላዊነታቸው መግለጫ ነው፡፡ 3. ሉዓላዊነታቸውም የሚገለጸው በዚህ ሕገ መንግሥት መሰረት በሚመርጧቸው ተወካዮቻቸውና በቀጥታ በሚያደርጉት ዴሞክራሲያዊ ተሳትፎ አማካይነት ይሆናል፡፡ አንቀጽ 9: የሕገ መንግሥት የበላይነት 1. ሕገ መንግሥቱ የሀገሪቱ የበላይ ሕግ ነው፡፡ ማንኛውም ሕግ፣ ልማዳዊ አሰራር፣እንዲሁም የመንግሥት አካል ወይም ባለሥልጣን ውሳኔ ከዚህ ሕገ መንግሥት ጋር የሚቃረን ከሆነ ተፈጻሚነት አይኖረውም፡፡ 2. ማንኛውም ዜጋ፣ የመንግሥት አካላት፣ የፖለቲካ ድርጅቶች፣ ሌሎች ማኅበራት እንዲሁም ባለሥልጣኖቻቸው፣ ሕገ መንግሥቱን የማስከበርና ለሕገ መንግሥቱ ተገዢ የመሆን ኃላፊነት አለባቸው፡፡ 3. በዚህ ሕገ መንግሥት ከተደነገገው ውጭ በማናቸውም አኳኊን የመንግሥት ሥልጣን መያዝ የተከለከለ ነው፡፡ 4. ኢትዮጵያ ያጸደቀቻቸው ዓለም አቀፍ ስምምነቶች የሀገሪቱ ሕግ አካል ናቸው፡፡ አንቀጽ 10: የሰብዓዊና ዴሞክራሲያዊ መብቶች 1. ሰብዓዊ መብቶችና ነጻነቶች ከሰው ልጅ ተፈጥሮ የሚመነጩ፣ የማይጣሱና የማይገፈፉ ናቸው፡፡ 2. የዜጐች እና የሕዝቦች ሰብዓዊና ዴሞክራሲያዊ መብቶች ይከበራሉ፡፡ አንቀጽ 11: የመንግሥትና የሃይማኖት መለያየት 1. መንግሥትና ሃይማኖት የተለያዩ ናቸው፡፡ 2. መንግሥታዊ ሃይማኖት አይኖርም፡፡ 3. መንግሥት በሃይማኖት ጉዳይ ጣልቃ አይገባም፡፡ ሃይማኖትም በመንግሥት ጉዳይ ጣልቃ አይገባም፡፡ አንቀጽ 12: የመንግሥት አሠራርና ተጠያቂነት 1. የመንግሥት አሠራር ለሕዝብ ግልጽ በሆነ መንገድ መከናወን አለበት፡፡ 2. ማንኛውም ኃላፊና የሕዝብ ተመራጭ ኃላፊነቱን ሲያጓድል ተጠያቂ ይሆናል፡፡ሕዝብ በመረጠው ተወካይ ላይ እምነት ባጣ ጊዜ ከቦታው ለማንሳት ይችላል፡፡ዝርዝሩ በሕግ ይወሰናል፡፡ ምዕራፍ ሦስት: መሰረታዊ መብቶችና ነጻነቶች አንቀጽ 13: ተፈጻሚነትና አተረጓጐም 1. በማንኛውም ደረጃ የሚገኙ የፌዴራል መንግሥትና የክልል ሕግ አውጪ፣ ሕግ አስፈጻሚ እና የዳኝነት አካሎች በዚህ ምዕራፍ የተካተቱን ድንጋጌዎች የማክበርና የማስከበር ኃላፊነትና ግዴታ አለባቸው፡፡ 2. በዚህ ምዕራፍ የተዘረዘሩት መሠረታዊ የመብቶችና የነጻነቶች ድንጋጌዎች ኢትዮጵያ ከተቀበለቻቸው ዓለም አቀፍ የሰብዓዊ መብቶች ሕግጋት፣ ዓለም አቀፍ የሰብዓዊ ስምምነቶችና ዓለም አቀፍ ሰነዶች መርሆዎች ጋር በተጣጣመ መንገድ ይተረጐማል፡፡ ክፍል አንድ ሰብዓዊ መብቶች አንቀጽ 14 የሕይወት፣ የአካል ደህንነትና የነጻነት መብት ማንኛውም ሰው ሰብዓዊ በመሆኑ የማይደፈርና የማይገሰስ በሕይወት የመኖር፣ የአካል ደህንነትና የነጻነት መብት አለው፡፡ አንቀጽ 15 የሕይወት መብት ማንኛውም ሰው በሕይወት የመኖር መብት አለው፡፡ ማንኛውም ሰው በሕግ በተደነገገ ከባድ የወንጀል ቅጣት ካልሆነ በስተቀር ሕይወቱን አያጣም፡፡ አንቀጽ 16 የአካል ደህንነት መብት ማንኛውም ሰው በአካሉ ላይ ጉዳት እንዳይደርስበት የመጠበቅ መብት አለው፡፡ አንቀጽ 17 የነጻነት መብት 1. በሕግ ከተደነገገው ሥርዓት ውጭ ማንኛውም ሰው ወንድም ሆነ ሴት ነጻነቱን ቷን አያጣም አታጣም፡፡ 2. ማንኛውም ሰው በሕግ ከተደነገገው ሥርዓት ውጭ ሊያዝ፣ ክስ ሳይቀርብበት ወይም ሳይፈረድበት ሊታሰር አይችልም፡፡ አንቀጽ 18 ኢሰብዓዊ አያያዝ ስለመከልከሉ 1. ማንኛውም ሰው ጭካኔ ከተሞላበት፣ ኢሰብዓዊ ከሆነ ወይም ክብሩን ከሚያዋርድ አያያዝ ወይም ቅጣት የመጠበቅ መብት አለው፡፡ 2. ማንኛውም ሰው በባርነት ወይም በግዴታ አገልጋይነት ሊያዝ አይችልም፡፡ለማንኛውም ዓላማ በሰው የመነገድ ተግባር የተከለከለ ነው፡፡ 3. ማንኛውም ሰው በኃይል ተገዶ ወይም ግዴታ ለማሟላት ማንኛውንም ሥራ እንዲሠራ ማድረግ የተከለከለ ነው፡፡ 4. በዚህ አንቀጽ ንዑስ አንቀጽ 3 በኃይል ተገዶ ወይም ግዴታን ለማሟላትየሚለው ሐረግ የሚከተሉትን ሁኔታዎች አያካትትም፤ ማንኛውም እስረኛ በእስራት ላይ ባለበት ጊዜ በሕግ መሠረት አንዲሠራ የተወሰነውን ወይም በገደብ ከእስር በተለቀቀበት ጊዜ፣ የሚሠራውን ማንኛውም ሥራ፣ ማንኛውም ወታደራዊ አገልግሎት ለመስጠት ሕሊናው የማይፈቅድለት ሰው በምትክ የሚሰጠውን አገልግሎት፣ የማኅበረሰቡን ሕይወት ወይም ደህንነት የሚያሰጋ የአስቸኳይ ጊዜ ሁኔታ ወይም አደጋ በሚያጋጥምበት ጊዜ የሚሰጥ ማንኛውም አገልግሎት፣ በሚመለከተው ሕዝብ ፈቃድ በአካባቢው የሚፈጸመውን ማንኛውንም ኢኮኖሚያዊና ማሕበራዊ የልማት ሥራ፡፡ አንቀጽ 19 የተያዙ ሰዎች መብት 1. ወንጀል ፈጽመዋል በመባል የተያዙ ሰዎች የቀረበባቸው ክስና ምክንያቶቹ በዝርዝር ወዲያውኑ በሚገባቸው ቋንቋ እንዲነገራቸው መብት አላቸው፡፡ 2. የተያዙ ሰዎች ላለመናገር መብት አላቸው፤ የሚሰጡት ማንኛውም ቃል ፍርድ ቤት በማስረጃነት ሊቀርብባቸው እንደሚችል መረዳት በሚችሉት ቋንቋ እንደተያዙ ወዲያውኑ ማስገንዘቢያ እንዲሰጣቸው መብት አላቸው፡፡ 3. የተያዙ ሰዎች በአርባ ስምንት ሰዓታት ውስጥ ፍርድ ቤት የመቅረብ መብት አላቸው፡፡ ይህም ጊዜ ሰዎቹ ከተያዙበት ቦታ ወደ ፍርድ ቤት ለመምጣት አግባብ ባለው ግምት የሚጠይቀውን ጊዜ አይጨምርም፡፡ ወዲያውኑ ፍርድ ቤት እንደቀረቡ በተጠረጠሩበት ወንጀል ለመታሰር የሚያበቃ ምክንያት ያለ መሆኑ ተለይቶ አንዲገለጽላቸው መብት አላቸው፡፡ 4. የያዛቸው የፖሊስ መኮንን ወይም የሕግ አስከባሪ በጊዜው ገደብ ፍርድ ቤት በማቅረብ የተያዙበትን ምክንያት ካላስረዳ፣ ፍርድ ቤቱ የአካል ነጻነታቸውን እንዲያስከብርላቸው የመጠየቅ ሊጣስ የማይችል መብት አላቸው፡፡ ሆኖም ፍትሕ እንዳይጓደል ሁኔታው የሚጠይቅ ከሆነ ፍርድ ቤቱ የተያዘው ሰው በጥበቃ ሥር እንዲቆይ ለማዘዝ ወይም ምርመራ ለማካሄድ ተጨማሪ የምርመራ ጊዜ ሲጠየቅ አስፈላጊ በሆነ መጠን ብቻ ሊፈቅድ ይችላል፡፡ የሚያስፈልገውን ተጨማሪ ጊዜ ፍርድ ቤቱ ሲወስን ኃላፊ የሆኑት የሕግ አስከባሪ ባለሥልጣኖች ምርመራውን አጣርተው የተያዘው ሰው በተቻለ ፍጥነት ፍርድ ቤት እንዲቀርብ ያለውን መብት የሚያስከብር መሆን አለበት፡፡ 5. የተያዙ ሰዎች በራሳቸው ላይ በማስረጃነት ሊቀርብ የሚችል የእምነት ቃል እንዲሰጡ ወይም ማናቸውንም ማስረጃ እንዲያምኑ አይገደዱም፡፡ በማስገደድ የተገኘ ማስረጃ ተቀባይነት አይኖረውም፡፡ 6. የተያዙ ሰዎች በዋስ የመፈታት መብት አላቸው፡፡ ሆኖም በሕግ በተደነገጉ ልዩ ሁኔታዎች ፍርድ ቤት ዋስትና ላለመቀበል ወይም በገደብ መፍታትን ጨምሮ በቂ የሆነ የዋስትና ማረጋገጫ እንዲቀርብ ለማዘዝ ይችላል፡፡ አንቀጽ 20 የተከሰሱ ሰዎች መብት 1. የተከሰሱ ሰዎች ክስ ከቀረበባቸው በኃላ ተገቢ በሆነ አጭር ጊዜ ውስጥ በመደበኛ ፍርድ ቤት ለሕዝብ ግልጽ በሆነ ችሎት የመሰማት መብት አላቸው፡፡ ሆኖም የተከራካሪዎቹን የግል ሕይወት፣ የሕዝብን የሞራል ሁኔታና የሀገሪቱን ደህንነት ለመጠበቅ ሲባል ብቻ ክርክሩ በዝግ ችሎት ሊሰማ ይችላል፡፡ 2. ክሱ በቂ በሆነ ዝርዝር እንዲነገራቸው እና ክሱን በጽሁፍ የማግኘት መብት አላቸው፡፡ 3. በፍርድ ሂደት ባሉበት ጊዜ በተከሰሱበት ወንጀል እንደ ጥፋተኛ ያለመቆጠር፣በምስክርነት እንዲቀርቡም ያለመገደድ መብት አላቸው፡፡ 4. የቀረበባቸውን ማናቸውንም ማስረጃ የመመልከት፣ የቀረቡባቸውን ምስክሮች የመጠየቅ፣ ለመከላከል የሚያስችላቸውን ማስረጃ የማቅረብ ወይም የማስቀረብ እንዲሁም ምስክሮቻቸው ቀርበው እንዲሰሙላቸው የመጠየቅ መብት አላቸው፡፡ 5. በመረጡት የሕግ ጠበቃ የመወከል ወይም ጠበቃ ለማቆም አቅም በማጣታቸው ፍትሕ ሊጓደል የሚችልበት ሁኔታ ሲያጋጥም ከመንግሥት ጠበቃ የማግኘት መብት አላቸው፡፡ 6. ክርክሩ በሚታይበት ፍርድ ቤት በተሰጠባቸው ትእዛዝ ወይም ፍርድ ላይ ሥልጣን ላለው ፍርድ ቤት ይግባኝ የማቅረብ መብት አላቸው፡፡ 7. የፍርዱ ሂደት በማይገባቸው ቋንቋ በሚካሄድበት ሁኔታ በመንግሥት ወጪ ክርክሩ እንዲተረጐምላቸው የመጠየቅ መብት አላቸው፡፡ አንቀጽ 21 በጥበቃ ሥር ያሉና በፍርድ የታሰሩ ሰዎች መብት 1. በጥበቃ ሥር ያሉና በፍርድ የታሰሩ ሰዎች ሰብዓዊ ክብራቸውን በሚጠብቁ ሁኔታዎች የመያዝ መብት አላቸው፡፡ 2. ከትዳር ጓደኞቻቸው፣ ከቅርብ ዘመዶቻቸው፣ ከጓደኞቻቸው፣ ከሃይማኖት አማካሪዎቻቸው፣ ከሐኪሞቻቸው እና ከሕግ አማካሪዎቸው ጋር ለመገናኘትና እንዲጐበቿቸውም ዕድል የማግኘት መብት አላቸው፡፡ አንቀጽ 22 የወንጀል ሕግ ወደኊላ ተመልሶ የማይሰራ ስለመሆኑ 1. ማንኛውም ሰው የወንጀል ክስ ሲቀርብበት የተከሰሰበት ድርጊት በተፈጸመበት ጊዜ ድርጊቱን መፈጸሙ ወይም አለመፈጸሙ ወንጀል መሆኑ በሕግ የተደነገገ ካልሆነ በስተቀር ሊቀጣ አይችልም፡፡ እንዲሁም ወንጀሉን በፈጸመበት ጊዜ ለወንጀሉ ተፈጻሚ ከነበረው የቅጣት ጣሪያ በላይ የከበደ ቅጣት በማንኛውም ሰው ላይ አይወሰንም፡፡ 2. የዚህ አንቀጽ ንዑስ አንቀጽ 1 ቢኖርም፣ ድርጊቱ ከተፈጸመ በኊላ የወጣ ሕግ ለተከሳሹ ወይም ለተቀጣው ሰው ጠቃሚ ሆኖ ከተገኘ ከድርጊቱ በኊላ የወጣው ሕግ ተፈጻሚነት ይኖረዋል፡፡ አንቀጽ 23 በአንድ ወንጀል ድጋሚ ቅጣት ስለመከልከሉ ማንኛውም ሰው በወንጀል ሕግና ሥነ ሥርዓት መሠረት ተከሶ የመጨረሻ በሆነ ውሳኔ ጥፋተኛነቱ በተረጋገጠበት ወይም በነጻ በተለቀቀበት ወንጀል እንደገና አይከሰስም ወይም አይቀጣም፡፡ አንቀጽ 24 የክብርና የመልካም ስም መብት 1. ማንኛውም ሰው ሰብዓዊ ክብሩና መልካም ስሙ የመከበር መብት አለው፡፡ 2. ማንኛውም ሰው የራሱን ስብዕና ከሌሎች ዜጐች መብቶች ጋር በተጣጣመ ሁኔታ በነጻ የማሳደግ መብት አለው፡፡ 3. ማንኛውም ሰው በማንኛውም ስፍራ በሰብዓዊነቱ እውቅና የማግኘት መብት አለው፡፡ አንቀጽ 25 የእኩልነት መብት ሁሉም ሰዎች በሕግ ፊት እኩል ናቸው፤ በመካከላቸውም ማንኛውም ዓይነት ልዩነት ሳይደረግ በሕግ እኩል ጥበቃ ይደረግላቸዋል፡፡ በዚህ ረገድ በዘር፣በብሔር፣ ብሔረሰብ፣በቀለም፣ በጾታ፣ በቋንቋ፣ በሃይማኖት፣ በፖለቲካ፣ በማኅበራዊ አመጣጥ፣ በሀብት፣በትውልድ ወይም በሌላ አቋም ምክንያት ልዩነት ሳይደረግ ሰዎች ሁሉ እኩልና ተጨባጭ የሕግ ዋስትና የማግኘት መብት አላቸው፡፡ አንቀጽ 26 የግል ሕይወት የመከበርና የመጠበቅ መብት 1. ማንኛውም ሰው የግል ሕይወቱ፣ ግላዊነቱ፣ የመከበር መብት አለው፡፡ ይህ መብት መኖሪያ ቤቱ፣ ሰውነቱና ንብረቱ ከመመርመር እንዲሁም በግል ይዞታው ያለ ንብረት ከመያዝ የመጠበቅ መብትን ያካትታል፡፡ 2. ማንኛውም ሰው በግል የሚጽፋቸውንና የሚጻጻፋቸው፣ በፖስታ የሚልካቸው ደብዳቤዎች፣ እንዲሁም በቴሌፎን፣ በቴሌኮሙኒኬሽንና በኤሌክትሮኒክስ መሣሪያዎች የሚያደርጋቸው ግንኙነቶች አይደፈሩም፡፡ 3. የመንግሥት ባለሥለጣኖች እነዚህን መብቶች የማክበርና የማስከበር ግዴታ አለባቸው፡፡ አስገዳጅ ሁኔታዎቸ ሲፈጠሩና ብሔራዊ ደህንነትን፣ የሕዝብን ሰላም፣ወንጀልን በመከላከል፣ ጤናንና የሕዝብን የሞራል ሁኔታ በመጠበቅ ወይም የሌሎችን መብትና ነጻነት በማስከበር ዓላማዎች ላይ በተመሰረቱ ዝርዝር ሕጐች መሰረት ካልሆነ በስተቀር የእነዚህ መብቶች አጠቃቀም ሊገደብ አይችለም፡፡ አንቀጽ 27 የሃይማኖት፣ የእምነትና የአመለካከት ነጻነት 1. ማንኛውም ሰው የማሰብ፣ የሕሊና እና የሃይማኖት ነጻነት አለው፡፡ ይህ መብት ማንኛውም ሰው የመረጠውን ሃይማኖት ወይም እምነት የመያዝ ወይም የመቀበል፣ ሃይማኖቱንና እምነቱን ለብቻ ወይም ከሌሎች ጋር በመሆን በይፋ ወይም በግል የማምለክ፣ የመከተል፣ የመተግበር፣ የማስተማር ወይም የመግለጽ መብትን ያካትታል፡፡ 2. በአንቀጽ 90 ንዑስ አንቀጽ 2 የተጠቀሰው አንደተጠበቀ ሆኖ የሃይማኖት ተከታዮች ሃይማኖታቸውን ለማስፋፋትና ለማደራጀት የሚያስችሏቸው የሃይማኖት ትምህርትና የአስተዳደር ተቋማት ማቋቋም ይችላሉ፡፡ 3. ማንኛውንም ሰው የሚፈልገውን እምነት ለመያዝ ያለውን ነጻነት በኃይል ወይም በሌላ ሁኔታ በማስገደድ መገደብ ወይም መከልከል አይቻልም፡፡ 4. ወላጆችና ሕጋዊ ሞግዚቶች በእምነታቸው መሰረት የሃይማኖታቸውንና የመልካም ሥነ ምግባር ትምህርት በመስጠት ልጆቻቸውን የማሳደግ መብት አላቸው፡፡ 5. ሃይማኖትና እምነትን የመግለጽ መብት ሊገደብ የሚችለው የሕዝብን ደህንነት፣ሰላምን፣ ጤናን፣ ትምህርትን፣ የሕዝብን የሞራል ሁኔታ፣ የሌሎች ዜችን መሰረታዊ መብቶች፣ ነጻነቶች እና መንግስት ከሃይማኖት ነጻ መሆኑን ለማረጋረገጥ በሚወጡ ሕጐች ይሆናል፡፡ አንቀጽ 28 በስብእና ስለሚፈደሙ ወንጀሎች 1. ኢትዮጵያ ባጸደቀቻቸው ዓለም አቀፍ ስምምነቶች እና በሌሎች የኢትዮጵያ ሕጐች በሰው ልጅ ላይ የተፈጸሙ ወንጀሎች ተብለው የተወሰኑትን ወንጀሎች፤የሰው ዘር የማጥፋት፣ ያለፍርድ የሞት ቅጣት እርምጃ የመውሰድ፣ በአስገዳጅ ሰውን የመሰወር፣ ወይም ኢሰብዓዊ የድብደባ ድርጊቶችን በፈጸሙ ሰዎች ላይ ክስ ማቅረብ በይርጋ አይታገድም፡፡ በሕግ አውጪው ክፍልም ሆነ በማንኛውም የመንግሥት አካል ውሳኔዎች በምሕረት ወይም በይቅርታ አይታለፉም፡፡ 2. ከዚህ በላይ የተደነገገው እንደተጠበቀ ሆኖ፣ በዚህ አንቀጽ ንዑስ አንቀጽ 1 የተቀሱትን ወንጀሎች ፈጽመው የሞት ቅጣት ለተፈረደባቸው ሰዎች ርዕሰ ብሔሩ ቅጣቱን ወደ ዕድሜ ልክ ጽኑ እስራት ሊያሻሽለው ይችላል፡፡ ዴሞክራሲያዊ መብቶች አንቀጽ 29 የአመለካከት እና ሐሳብን በነጻ የመያዝና የመግለጽ መብት 1. ማንኛውም ሰው ያለማንም ጣልቃ ገብነት የመሰለውን አመለካከት ለመያዝ ይችላል፡፡ 2. ማንኛውም ሰው ያለማንም ጣልቃ ገብነት ሐሳቡን የመግለጽ ነጻነት አለው፡፡ ይህ ነጻነት በሀገር ውስጥም ሆነ ከሀገር ውጭ ወሰን ሳይደረግበት በቃልም ሆነ በጽሑፍ ወይም በሕትመት፣ በሥነ ጥበብ መልክ ወይም በመረጠው በማንኛውም የማሰራጫ ዘዴ፣ ማንኛውንም ዓይነት መረጃና ሐሳብ የመሰብሰብ፣ የመቀበልና የማሰራጨት ነጻነቶችን የካትታል፡፡ 3. የኘሬስና የሌሎች መገናኛ ብዙኃን፣ እንዲሁም የሥነ ጥበብ ፈጠራ ነጻነት ተረጋግጧል፡፡ የኘሬስ ነጻነት በተለይ የሚከተሉትን መብቶች ያጠኝልላል፣ የቅድሚያ ምርመራ በማንኛውም መልኩ የተከለከለ መሆኑን፣ የሕዝብን ጥቅም የሚመለከት መረጃ የማግኘት ዕድልን፡፡ 4. ለዴሞክራሲያዊ ሥርዓት አስፈላጊ የሆኑ መረጃዎች፣ ሐሳቦችና አመለካከቶች በነጻ መንሸራሸራቸውን ለማረጋገጥ ሲባል ኘሬስ በተቋምነቱ የአሠራር ነጻነትና የተለያዩ አስተያየቶች የማስተናገድ ችሎታ እንዲኖረው የሕግ ጥበቃ ይደረግለታል፡፡ 5. በመንግሥት ገንዘብ የሚካሄድ ወይም በመንግሥት ቁጥጥር ሥር ያለ መገናኛ ብዙኃን የተለያዩ አስተያየቶችን ለማስተናገድ በሚያስችለው ሁኔታ እንዲመራ ይደረጋል፡፡ 6. እነዚህ መብቶች ገደብ ሊጣልባቸው የሚችለው የሀሳብና መረጃ የማግኘት ነጻነት በአስተሳሰባዊ ይዘቱና ሊያስከትል በሚችለው አስተሳሰባዊ ውጤት ሊገታ አይገባውም በሚል መርህ ላይ ተመስርተው በሚወጡ ሕጐች ብቻ ይሆናል፡፡ የወጣቶችን ደህንነት፣ የሰውን ክብርና መልካም ስም ለመጠበቅ ሲባል ሕጋዊ ገደቦች በነዚህ መብቶች ላይ ሊደነገጉ ይችላሉ፡፡ የጦር ቅስቃሴዎች እንዲሁም ሰብዓዊ ክብርን የሚነኩ የአደባባይ መግለጫዎች በህግ የሚከለከሉ ይሆናል፡፡ 7. ማንኛውም ዜጋ ከላይ በተጠቀሱት መብቶች አጠቃቀም ረገድ የሚጣሉ ሕጋዊ ገደቦችን ጥሶ ከተገኘ በሕግ ተጠያቂ ሊሆን የችላል፡፡ አንቀጽ 30 የመሰብሰብ፣ ሰላማዊ ሰልፍ የማድረግ ነጻነትና አቤቱታ የማቅረብ መብት 1. ማንኛውም ሰው ከሌሎች ጋር በመሆን መሣሪያ ሳይዝ በሰላም የመሰብሰብ፣ሰላማዊ ሰልፍ የማድረግ ነጻነትና፣ አቤቱታ የማቅረብ መብት አለው፡፡ ከቤት ውጭ የሚደረጉ ስብሰባዎችና ሰላማዊ ሰልፎች በሚንቀሳቀሱባቸው ቦታዎች በሕዝብ እንቅስቃሴ ላይ ችግር እንዳይፈጥሩ ለማድረግ ወይም በመካሔድ ላይ ያለ ስብሰባ ወይም ሰላማዊ ሰልፍ ሰላምን፣ ዴሞክራሲያዊ መብቶችንና የሕዝብን የሞራል ሁኔታ እንዳይጥሱ ለማስጠበቅ አግባብ ያላቸው ሥርዓቶች ሊደነገጉ ይችላሉ፡፡ 2. ይህ መብት የወጣቶችን ደህንነት፣ የሰውን ክብርና መልካም ስምን ለመጠበቅ፣የጦርነት ቅስቀሳዎች እንዲሁም ሰብዓዊ ክብርን የሚነኩ የአደባባይ መግለጫዎችን ለመከላከል ሲባል በሚወጡ ሕጐች መሰረት ተጠያቂ ከመሆን አያድንም፡፡ አንቀጽ 31 የመደራጀት መብት ማንኛውም ሰው ለማንኛውም ዓላማ በማኅበር የመደራጀት መብት አለው፡፡ ሆኖም አግባብያለውን ሕግ በመጣስ ወይም ሕገ መንግሥታዊ ሥርዓቱን በሕገ ወጥ መንገድ ለማፍረስ የተመሰረቱ ወይም የተጠቀሱትን ተግባራት የሚያራምዱ ድርጅቶች የተከለከሉ ይሆናሉ፡፡ አንቀጽ 32 የመዘዋወር ነጻነት 1. ማንኛውም ኢትዮጵያዊ ወይም በሕጋዊ መንገድ ሀገሪቱ ውስጥ የሚገኝ የውጭ ዜጋ በመረጠው የሀገሪቱ አካባቢ የመዘዋወርና የመኖሪያ ቦታ የመመስረት፣እንዲሁም በፈለገው ጊዜ ከሀገር የመውጣት ነጻነት አለው፡፡ 2. ማንኛውም ኢትዮጵያዊ ወደ ሀገሩ የመመለስ መብት አለው፡፡ አንቀጽ 33 የዜግነት መብቶች 1. ማንኛውም ኢትዮጵያዊ ኢትዮጵያዊት ከፈቃዱ ከፈቃዷ ውጭ ኢትዮጵያዊ ዜግነቱን ዜግነትዋን ሊገፈፍ ወይም ልትገፈፍ አይችልም አትችልም፡፡ኢትዮጵያዊ ኢትዮጵያዊት ዜጋ ከሌላ ሀገር ዜጋ ጋር የሚፈጽመው የምጽትፈጽመው ጋብቻ ኢትዮጵያዊ ዜግነቱን ዜግነትዋን አያስቀርም፡፡ 2. ማንኛውም ኢትዮጵያዊ ዜጋ የኢትዮጵያ ዜግነት በሕግ የሚያስገኘውን መብት ጥበቃና ጥቅም የማግኘት መብት አለው፡፡ 3. ማንኛውም ዜጋ ኢትዮጵያዊ ዜግነቱን የመለወጥ መብት አለው፡፡ 4. ኢትዮጵያ ከአጸደቀቻቸው ዓለም አቀፍ ስምምነቶች ጋር በማይቃረን መንገድ በሚወጣ ሕግ እና በሚደነገግ ሥርዓት መሰረት የኢትዮጵያ ዜግነት ለውጭ ሀገር ሰዎች ሊሰጥ ይችላል፡፡ አንቀጽ 34 የጋብቻ፣ የግልና የቤተሰብ መብቶች 1. በሕግ ከተወሰነው የጋብቻ ዕድሜ የደረሱ ወንዶችና ሴቶች በዘር፣ በበሔር፣በብሔረሰብ ወይም በሃይማኖት ልዩነት ሳይደረግባቸው የማግባትና ቤተሰብ የመመስረት መብት አላቸው፡፡ በጋብቻ አፈጻጸም፣ በጋብቻው ዘመንና በፍቺ ጊዜ እኩል መብት አላቸው፡፡ በፍቺም ጊዜ የልጆችን መብትና ጥቅም እንዲከበር የሚያደርጉ ድንጋጌዎች ይደነገጋሉ፡፡ 2. ጋብቻ በተጋቢዎች ነጻና ሙሉ ፈኝድ ላይ ብቻ ይመሰረታል፡፡ 3. ቤተሰብ የኅብረተሰብ የተፈጥሮ መሰረታዊ መነሻ ነው፡፡ ከኅብረተሰብና ከመንግሥት ጥበቃ የማግኘት መብት አለው፡፡ 4. በሕግ በተለይ በሚዘረዘረው መሰረት በሃይማኖት፣ በባሕል የሕግ ሥርዓቶች ላይ ተመስርትው ለሚፈጸሙ ጋብቻዎች እውቅና የሚሰጥ ሕግ ሊወጣ ይችላል፡፡ 5. ይህ ሕገ መንግሥት የግል እና የቤተሰብ ሕግን በተመለከተ በተከራካሪዎች ፈቃድ በሃይማኖቶች ወይም በባሕሎች ሕጐች መሰረት መዳኘትን አይከለክልም፡፡ ዝርዝሩ በሕግ ይወሰናል፡፡ አንቀጽ 35 የሴቶች መብት 1. ሴቶች ይህ ሕገ መንግሥት በአረጋገጣቸው መብቶችና ጥበቃዎች በመጠቀም ረገድ ከወንዶች ጋር እኩል መብት አላቸው፡፡ 2. ሴቶች በዚህ ሕገ መንግሥት በተደነገገው መሰረት በጋብቻ ከወንዶች ጋር እኩል መብት አላቸው፡"
print(len(split_into_sentences_amharic(sentences)))
# --- MODIFIED CHUNKING FUNCTION ---
def chunk_text_by_sentences(text: str, max_sentences_per_chunk: int = 10) -> list[str]:
    """
    Splits text into chunks, each containing approximately max_sentences_per_chunk.
    """
    sentences = split_into_sentences_amharic(text)
    chunks = []
    current_chunk_sentences = []

    for sentence in sentences:
        current_chunk_sentences.append(sentence)
        
        # If we have reached the desired number of sentences or this is the last sentence
        if len(current_chunk_sentences) >= max_sentences_per_chunk or sentence == sentences[-1]:
            combined_chunk = " ".join(current_chunk_sentences).strip()
            if combined_chunk: # Add only non-empty chunks
                chunks.append(combined_chunk)
            current_chunk_sentences = [] # Reset for next chunk

    # Filter out any lingering empty strings just in case
    return [chunk for chunk in chunks if chunk]


# --- Main Ingestion Function ---
def ingest_document(
    file_path: str,
    collection_name: str,
    max_sentences_per_chunk: int = 5, # New parameter for sentence-based chunking
):
    """
    Uploads a file, extracts text, cleans, chunks, and stores it in ChromaDB.
    Deletes existing collection to ensure embedding dimension compatibility.
    """
    if not ingestion_chroma_client or not ingestion_embedder:
        return {"status": "error", "message": "ChromaDB client or embedder not initialized."}

    try:
        print(f"🔄 Processing file: {file_path}")

        # 1. Extract raw text from file
        raw_text = ""
        if file_path.endswith('.pdf'):
            doc = fitz.open(file_path)
            for page in doc:
                raw_text += page.get_text() + "\n" # Add newline between pages
            doc.close()
        elif file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_text = f.read()
        else:
            raise ValueError("Unsupported file type. Only .txt and .pdf are supported for ingestion.")

        if not raw_text.strip():
            return {"status": "error", "message": "Extracted text is empty. File might be empty or unreadable."}

        # 2. Apply cleaning and normalization
        cleaned_text = remove_common_headers(raw_text)
        cleaned_text = clean_text_and_normalize_whitespace(cleaned_text)
        
        # 3. Extract specific Amharic text if any other language might be present
        processed_text = extract_amharic_text_only(cleaned_text)
        
        if not processed_text.strip():
            return {"status": "error", "message": "No meaningful text found after Amharic extraction/cleaning."}

        # 4. Chunk text into smaller, manageable pieces for embedding
        # Pass the new parameter here
        chunks = chunk_text_by_sentences(processed_text, max_sentences_per_chunk=max_sentences_per_chunk)
        
        if not chunks:
            return {"status": "error", "message": "No chunks generated from the document after processing."}

        print(f"✅ Text chunked into {len(chunks)} pieces.")

        # 5. Delete existing collection and create a new one (crucial for dimension change)
        try:
            ingestion_chroma_client.delete_collection(name=collection_name)
            print(f"🧹 Old collection '{collection_name}' deleted to ensure dimension compatibility.")
        except Exception as e:
            print(f"Collection '{collection_name}' not found or could not be deleted (might be new): {e}")

        collection = ingestion_chroma_client.create_collection(name=collection_name)
        print(f"🆕 New collection '{collection_name}' created.")

        # 6. Prepare data for ChromaDB
        documents_to_add = []
        metadatas_to_add = []
        ids_to_add = []
        embeddings_to_add = []

        print("Embedding and adding chunks to ChromaDB...")
        for i, chunk_content in enumerate(chunks):
            doc_text = chunk_content
            doc_id = f"{os.path.basename(file_path)}_{i}"
            
            doc_metadata = {
                "source_file": os.path.basename(file_path),
                "chunk_index": i,
                "pages": "" # Still empty string as we're not tracking page numbers per chunk with this method
            }
            
            embedding = ingestion_embedder.encode(doc_text).tolist()

            documents_to_add.append(doc_text)
            metadatas_to_add.append(doc_metadata)
            ids_to_add.append(doc_id)
            embeddings_to_add.append(embedding)

        if documents_to_add:
            collection.add(
                documents=documents_to_add,
                metadatas=metadatas_to_add,
                ids=ids_to_add,
                embeddings=embeddings_to_add
            )
            print(f"✅ Successfully added {len(documents_to_add)} chunks to ChromaDB collection '{collection_name}'.")
        else:
            print("No documents to add to ChromaDB after processing.")

        return {"status": "success", "message": f"Successfully ingested {len(documents_to_add)} chunks from {os.path.basename(file_path)}."}

    except Exception as e:
        print(f"An error occurred during data ingestion: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"An error occurred during data ingestion: {e}"}
