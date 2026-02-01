from agent.tools.web_search import WebSearchTool

def test():
    print("--- Testing Search Logic ---")
    tool = WebSearchTool()
    # verify the tool logic itself
    res = tool.search("who is the president of USA")
    print(res)

if __name__ == "__main__":
    test()
