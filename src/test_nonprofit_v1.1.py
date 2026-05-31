import unittest
import mysql.connector

class TestDatabaseConnection(unittest.TestCase):
    def test_connection(self):
        try:
            conn = mysql.connector.connect(
                host='localhost',
                database='nonprofit_db',
                user='root',
                password='root123'   # use your actual password
            )
            conn.close()
            connected = True
        except:
            connected = False
        self.assertTrue(connected, "Database connection failed")

    def test_count_people_served(self):
        conn = mysql.connector.connect(
            host='localhost', database='nonprofit_db',
            user='root', password='root123'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM people_served")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        self.assertIsInstance(count, int)

if __name__ == '__main__':
    unittest.main()