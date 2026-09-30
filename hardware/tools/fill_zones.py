import sys, pcbnew
path = sys.argv[1]
board = pcbnew.LoadBoard(path)
filler = pcbnew.ZONE_FILLER(board)
ok = filler.Fill(board.Zones())
pcbnew.SaveBoard(path, board)
print("filled ok")
