from src.merkle import merkle_tree

class Val:
    def __init__(self, hash_val):
        self.hash_val = hash_val

    def get_hash(self):
        return self.hash_val

    def __str__(self):
        return str(self.hash_val)

if __name__ == '__main__':
    print(merkle_tree([Val(bytes([i])) for i in range(10)]))
