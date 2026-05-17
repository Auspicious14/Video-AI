import json

def extract_json(text):
    # Robust JSON extraction: look for first '{' and last '}'
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx:end_idx + 1]
    return text

def test():
    # Case 1: Standard markdown
    text1 = "```json\n{\"key\": \"value\"}\n```"
    assert json.loads(extract_json(text1)) == {"key": "value"}
    
    # Case 2: Markdown with extra text
    text2 = "Here is the JSON:\n```json\n{\"key\": \"value\"}\n```\nHope it helps!"
    assert json.loads(extract_json(text2)) == {"key": "value"}
    
    # Case 3: No markdown
    text3 = "{\"key\": \"value\"}"
    assert json.loads(extract_json(text3)) == {"key": "value"}
    
    # Case 4: Unterminated string (the error user had, but should be fixed by JSON mode)
    # The fix I added won't magically fix a cut-off string, but it will extract it correctly if it's there.
    # The real fix is "response_mime_type": "application/json" which prevents the unterminated string in the first place.
    text4 = "Some prefix { \"hook\": \"hello\" } suffix"
    assert json.loads(extract_json(text4)) == {"hook": "hello"}

    print("All tests passed!")

if __name__ == "__main__":
    test()
