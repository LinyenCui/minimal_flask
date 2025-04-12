from models import db

class Client(db.Model):
    __tablename__ = 'clients'
    
    client_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(60))  # 客户名称
    address = db.Column(db.String(120))  # 地址
    short_name = db.Column(db.String(30), unique=True)  # 简称，用于快速引用
    category = db.Column(db.String(30))  # 分类：东洋/诊所/其他
    remarks = db.Column(db.String(90))  # 备注
    
    def __repr__(self):
        return f"<Client {self.short_name}>" 