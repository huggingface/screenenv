from screenenv import MCPRemoteServer

if __name__ == "__main__":
    try:
        server = MCPRemoteServer()
    except Exception as e:
        print(e)
    finally:
        server.close()
